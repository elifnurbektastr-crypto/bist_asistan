"""yfinance (fiyat, temettü, kur) ve TCMB EVDS (makro) veri çekme.

Akış: önce önbelleğe bakılır, gerekirse sadece eksik günler indirilir (artımlı güncelleme).
Yahoo zaman zaman istekleri sınırladığı için boş dönen semboller artan beklemeyle
yeniden denenir; erişim tamamen engellenmişse indirme erken durdurulur.
"""

import logging
import os
import time
from pathlib import Path

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

from src import config
from src.data import cache

log = logging.getLogger(__name__)

YF_SUTUNLARI = ["Open", "High", "Low", "Close", "Adj Close", "Volume", "Dividends", "Stock Splits"]
FIYAT_KLASORU = "fiyat"
ARTIMLI_ORTUSME_GUNU = 10   # artımlı güncellemede geriye doğru tekrar indirilen gün sayısı
DEVRE_KESICI = 3            # üst üste bu kadar sembol gelmezse indirmeyi durdur


# ---------------------------------------------------------------------------
# Saf (internetsiz) dönüşümler — testler bunları doğrular
# ---------------------------------------------------------------------------

def standartlastir(ham: pd.DataFrame) -> pd.DataFrame:
    """yfinance çıktısını projenin standart fiyat tablosuna çevirir.

    Varsayım (quality.bolunme_kontrolu ile doğrulanır): yfinance 'Close' bölünmeye göre
    düzeltilmiştir, 'Adj Close' ise bölünme + temettü düzeltilmiştir.

    Çıktı sütunları:
      acilis, yuksek, dusuk, kapanis, hacim : o gün gerçekte işlem gören (ham) değerler
      duz_acilis ... duz_kapanis            : bölünme + temettü düzeltilmiş (getiri hesapları için)
      temettu      : hak kullanım günündeki hisse başı brüt temettü, o günkü TL karşılığı
      temettu_duz  : aynı temettü, bugünkü hisse sayısı bazında (verim hesapları için)
      bolunme      : bölünme oranı (ör. 2.0 = 1 hisse 2 hisse oldu), yoksa 0
    """
    df = ham.copy()
    for sutun in ["Dividends", "Stock Splits"]:
        if sutun not in df:
            df[sutun] = 0.0
    if "Adj Close" not in df:
        df["Adj Close"] = df["Close"]
    df = df[YF_SUTUNLARI].dropna(subset=["Close"])

    # Saat dilimini at, sadece tarih kalsın
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_convert(config.SAAT_DILIMI).tz_localize(None)
    df.index = idx.normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index()

    bolunme = df["Stock Splits"].fillna(0.0)
    oran = bolunme.where(bolunme > 0, 1.0)
    # t gününün ham fiyatı = düzeltilmiş fiyat × (t'den SONRAKİ bölünme oranlarının çarpımı)
    sonraki_bolunmeler = oran[::-1].cumprod()[::-1].shift(-1, fill_value=1.0)
    temettu_orani = df["Adj Close"] / df["Close"]

    cikti = pd.DataFrame(index=df.index)
    cikti.index.name = "tarih"
    for yf_ad, ad in [("Open", "acilis"), ("High", "yuksek"), ("Low", "dusuk"), ("Close", "kapanis")]:
        cikti[ad] = df[yf_ad] * sonraki_bolunmeler
    cikti["hacim"] = df["Volume"] / sonraki_bolunmeler
    for yf_ad, ad in [("Open", "duz_acilis"), ("High", "duz_yuksek"), ("Low", "duz_dusuk")]:
        cikti[ad] = df[yf_ad] * temettu_orani
    cikti["duz_kapanis"] = df["Adj Close"]
    cikti["temettu"] = df["Dividends"].fillna(0.0) * sonraki_bolunmeler
    cikti["temettu_duz"] = df["Dividends"].fillna(0.0)
    cikti["bolunme"] = bolunme
    return cikti


def tatil_satirlarini_at(df: pd.DataFrame) -> pd.DataFrame:
    """Hacmi sıfır olan günleri atar (resmi tatiller, işlem durdurmaları).

    Yahoo tatil günlerini önceki fiyatla doldurup ekliyor: bu sahte günler volatiliteyi
    düşük gösterir ve 'N işlem günü sonrası' hedeflerini kaydırır.
    Hacmi hiç olmayan seriler (ör. döviz kuru) olduğu gibi bırakılır.
    """
    if df.empty or (df["hacim"] > 0).mean() < 0.5:
        return df
    return df[df["hacim"] > 0]


def elle_duzeltmeleri_uygula(df: pd.DataFrame, duzeltmeler: pd.DataFrame) -> pd.DataFrame:
    """Yahoo'nun kaçırdığı ya da yanlış oranla kaydettiği bölünmeleri düzeltir.

    Her iki durumda da ham fiyatlar doğrudur (Yahoo'nun kendi oranıyla geri çevrildikleri
    için); bozuk olan düzeltilmiş seridir. Bölünme tarihinden ÖNCEKİ düzeltilmiş fiyatlar
    ve bugünkü bazdaki temettüler (doğru oran / Yahoo'nun oranı) katsayısına bölünür.
    Yahoo hiç kaydetmemişse Yahoo'nun oranı 1 sayılır. Okuma anında uygulanır.
    duzeltmeler: 'tarih' ve 'oran' sütunları (ör. 10 = 1 hisse 10 hisse oldu)
    """
    if duzeltmeler is None or duzeltmeler.empty:
        return df
    df = df.copy()
    for _, satir in duzeltmeler.iterrows():
        tarih, oran = pd.Timestamp(satir["tarih"]), float(satir["oran"])
        if tarih not in df.index:
            continue
        yahoo_orani = df.loc[tarih, "bolunme"] or 1.0
        katsayi = oran / yahoo_orani
        once = df.index < tarih
        for sutun in ["duz_acilis", "duz_yuksek", "duz_dusuk", "duz_kapanis", "temettu_duz"]:
            df.loc[once, sutun] = df.loc[once, sutun] / katsayi
        df.loc[tarih, "bolunme"] = oran
    return df


def elle_duzeltmeler(kod: str) -> pd.DataFrame:
    """referans/duzeltmeler.csv içinden bir hisseye ait satırları döner."""
    dosya = config.REFERANS_DIZINI / "duzeltmeler.csv"
    if not dosya.exists():
        return pd.DataFrame(columns=["kod", "tarih", "oran"])
    tablo = pd.read_csv(dosya, comment="#")
    return tablo[tablo["kod"].str.upper() == kod.replace(".IS", "").upper()]


def tamamlanmamis_cubugu_at(df: pd.DataFrame, simdi: pd.Timestamp | None = None) -> pd.DataFrame:
    """Seans bitmeden alınan bugünkü çubuğu atar.

    Seans içinde gelen 'bugün' satırı kesinleşmemiş fiyattır. Bunu kullanmak
    backtest'te geleceği görmek (look-ahead) anlamına gelebilir.
    """
    if df.empty:
        return df
    simdi = simdi or pd.Timestamp.now(tz=config.SAAT_DILIMI)
    bugun = simdi.tz_localize(None).normalize() if simdi.tz else simdi.normalize()
    kapanis = pd.Timestamp(f"{bugun.date()} {config.SEANS_KAPANIS_SAATI}")
    simdi_yerel = simdi.tz_localize(None) if simdi.tz else simdi
    if df.index[-1] == bugun and simdi_yerel < kapanis:
        return df.iloc[:-1]
    return df


def artimli_birlestir(eski: pd.DataFrame, yeni: pd.DataFrame, tolerans: float = 1e-4) -> pd.DataFrame | None:
    """Önbellekteki veriyle yeni indirilen parçayı birleştirir.

    Ortak günlerde fiyatlar uyuşmuyorsa ya da yeni parçada bölünme/temettü varsa
    tüm geçmişin düzeltme katsayıları değişmiştir: None döner (tam indirme gerekir).
    """
    if yeni.empty:
        return eski
    ortak = eski.index.intersection(yeni.index)
    if len(ortak) == 0:
        return None
    for sutun in ["kapanis", "duz_kapanis"]:
        fark = (eski.loc[ortak, sutun] / yeni.loc[ortak, sutun] - 1).abs()
        if (fark > tolerans).any():
            return None
    yeni_kisim = yeni[yeni.index > eski.index[-1]]
    if (yeni_kisim["bolunme"] > 0).any() or (yeni_kisim["temettu"] > 0).any():
        return None
    return pd.concat([eski[eski.index < yeni.index[0]], yeni])


# ---------------------------------------------------------------------------
# İnternetten indirme
# ---------------------------------------------------------------------------

def _tek_indir(sembol: str, baslangic: str, deneme: int = 3, bekleme: float = 5.0) -> pd.DataFrame | None:
    """Tek sembolü artan beklemeyle (5, 10 sn) yeniden deneyerek indirir.

    Ticker.history kullanılır: toplu yf.download hisselerde bile temettü/bölünme
    sütunlarını döndürmüyordu, bu da ham fiyat ve temettü hesaplarını sessizce bozar.
    """
    for k in range(deneme):
        try:
            tablo = yf.Ticker(sembol).history(start=baslangic, auto_adjust=False, actions=True)
            # Not: temettü/bölünmesi olmayan semboller (endeks, kur) için Yahoo bu
            # sütunları hiç göndermiyor; standartlastir() eksikleri 0 ile doldurur.
            if not tablo.empty:
                return tablo
        except Exception as hata:
            log.debug("%s deneme %d hata: %s", sembol, k + 1, hata)
        if k < deneme - 1:
            time.sleep(bekleme * (k + 1))
    return None


def _indir(semboller: list[str], baslangic: str) -> dict[str, pd.DataFrame]:
    """Sembolleri sırayla indirir.

    Devre kesici: üst üste DEVRE_KESICI sembol hiç gelmezse Yahoo bizi engelliyor
    demektir; kalanlar denenmez (dakikalarca boşuna beklememek için).
    """
    sonuc: dict[str, pd.DataFrame] = {}
    basarisiz: list[str] = []
    ust_uste_basarisiz = 0
    for i, s in enumerate(semboller):
        tablo = _tek_indir(s, baslangic)
        if tablo is None:
            basarisiz.append(s)
            ust_uste_basarisiz += 1
            if ust_uste_basarisiz >= DEVRE_KESICI:
                log.error("Üst üste %d sembol indirilemedi; Yahoo erişimi engelliyor olabilir. "
                          "Kalan %d sembol atlandı.", DEVRE_KESICI, len(semboller) - i - 1)
                return sonuc
            continue
        ust_uste_basarisiz = 0
        sonuc[s] = tablo
        time.sleep(1)  # istekler arasında kısa bekleme

    # İkinci tur: oturumun ilk istekleri sık sık boş dönüyor, sonradan aynı sembol geliyor
    for s in basarisiz:
        tablo = _tek_indir(s, baslangic)
        if tablo is not None:
            sonuc[s] = tablo
    return sonuc


def _bugun_guncellendi_mi(ad: str, klasor: str = FIYAT_KLASORU, dizin: Path | None = None,
                          simdi: pd.Timestamp | None = None) -> bool:
    """Önbellek bugünün verisini içeriyor sayılabilir mi?

    Seans kapanmadan önce: bugün yazıldıysa yeterli (yeni kesin veri yok).
    Seans kapandıktan sonra: ancak kapanıştan SONRA yazıldıysa yeterli; yoksa gün içinde
    yazılmış önbellek bugünün kapanışını kaçırır.
    """
    zaman = cache.guncelleme_tarihi(ad, klasor, dizin)
    if zaman is None:
        return False
    simdi = simdi or pd.Timestamp.now(tz=config.SAAT_DILIMI)
    zaman = zaman.tz_convert(config.SAAT_DILIMI)
    if zaman.date() != simdi.date():
        return False
    kapanis = pd.Timestamp(f"{simdi.date()} {config.SEANS_KAPANIS_SAATI}", tz=config.SAAT_DILIMI)
    return simdi < kapanis or zaman >= kapanis


def fiyat_verisi(semboller: list[str], baslangic: str = config.BASLANGIC_TARIHI,
                 yenile: bool = False, dizin: Path | None = None) -> dict[str, pd.DataFrame]:
    """Sembollerin standart fiyat tablolarını döner (önbellek + artımlı güncelleme).

    semboller: yfinance sembolleri ya da BIST kodları (THYAO veya THYAO.IS)
    yenile: True ise önbellek yok sayılır, tüm geçmiş yeniden indirilir.
    """
    semboller = [config.yf_sembol(s) for s in semboller]
    sonuc: dict[str, pd.DataFrame] = {}
    artimli: dict[str, pd.DataFrame] = {}
    tam: list[str] = []

    for s in semboller:
        eski = None if yenile else cache.oku(s, FIYAT_KLASORU, dizin)
        if eski is not None and _bugun_guncellendi_mi(s, FIYAT_KLASORU, dizin):
            sonuc[s] = eski
        elif eski is not None and not eski.empty:
            artimli[s] = eski
        else:
            tam.append(s)

    # 1) Artımlı güncelleme
    if artimli:
        en_eski = min(df.index[-1] for df in artimli.values())
        baslangic_artimli = (en_eski - pd.Timedelta(days=ARTIMLI_ORTUSME_GUNU)).strftime("%Y-%m-%d")
        indirilen = _indir(list(artimli), baslangic_artimli)
        for s, eski in artimli.items():
            if s not in indirilen:
                log.warning("%s güncellenemedi, önbellekteki eski veri kullanılıyor.", s)
                sonuc[s] = eski
                continue
            yeni = tamamlanmamis_cubugu_at(tatil_satirlarini_at(standartlastir(indirilen[s])))
            birlesik = artimli_birlestir(eski, yeni)
            if birlesik is None:
                log.info("%s: yeni bölünme/temettü ya da düzeltme farkı, tamamı yeniden indirilecek.", s)
                tam.append(s)
            else:
                cache.yaz(birlesik, s, FIYAT_KLASORU, dizin)
                sonuc[s] = birlesik

    # 2) Tam indirme
    if tam:
        indirilen = _indir(tam, baslangic)
        for s in tam:
            if s not in indirilen:
                eski = cache.oku(s, FIYAT_KLASORU, dizin)
                if eski is not None:
                    log.warning("%s indirilemedi, önbellekteki eski veri kullanılıyor.", s)
                    sonuc[s] = eski
                else:
                    log.error("%s indirilemedi ve önbellekte yok.", s)
                continue
            df = tamamlanmamis_cubugu_at(tatil_satirlarini_at(standartlastir(indirilen[s])))
            cache.yaz(df, s, FIYAT_KLASORU, dizin)
            sonuc[s] = df

    # Temizlik ve elle düzeltmeler okuma anında uygulanır (önbellek ham kalır)
    return {s: elle_duzeltmeleri_uygula(tatil_satirlarini_at(df), elle_duzeltmeler(s))
            for s, df in sonuc.items()}


# ---------------------------------------------------------------------------
# Makro veri
# ---------------------------------------------------------------------------

def usdtry(baslangic: str = config.BASLANGIC_TARIHI, yenile: bool = False) -> pd.Series | None:
    """USD/TRY günlük kapanış serisini döner (yfinance 'TRY=X')."""
    veri = fiyat_verisi([config.USDTRY], baslangic, yenile)
    df = veri.get(config.USDTRY)
    return None if df is None else df["kapanis"].rename("usdtry")


def evds_verisi(baslangic: str = config.BASLANGIC_TARIHI, yenile: bool = False) -> pd.DataFrame | None:
    """TÜFE ve politika faizi serilerini TCMB EVDS'ten çeker.

    EVDS_API_KEY yoksa ya da istek başarısız olursa uyarı verir ve None döner;
    uygulamanın geri kalanı makro veri olmadan çalışmaya devam eder.

    'yayin_tarihi' sütunu: TÜFE ay bittikten sonra (ertesi ayın 3'ünde) açıklanır.
    Özelliklerde bu tarih kullanılmazsa model henüz açıklanmamış veriyi görmüş olur (look-ahead).
    """
    if not yenile:
        onbellek = cache.oku("evds", "makro")
        if onbellek is not None and _bugun_guncellendi_mi("evds", "makro"):
            return onbellek

    load_dotenv(config.KOK_DIZIN / ".env")
    anahtar = os.getenv("EVDS_API_KEY", "").strip()
    if not anahtar:
        log.warning("EVDS_API_KEY tanımlı değil; TÜFE ve politika faizi atlanıyor.")
        return cache.oku("evds", "makro")

    try:
        from evds import evdsAPI
        api = evdsAPI(anahtar)
        tablolar = []
        for ad, kod in config.EVDS_SERILERI.items():
            parcalar = []
            for bas, son in evds_parcalari(baslangic, pd.Timestamp.today(), config.EVDS_PARCA_YIL):
                # Not: evds paketi bitiş tarihi verilmezse onu başlangıca eşitliyor (tek gün döner)
                ham = api.get_data([kod], startdate=bas.strftime("%d-%m-%Y"), enddate=son.strftime("%d-%m-%Y"))
                if ham is not None and len(ham):
                    parcalar.append(_evds_tablosunu_duzenle(ham, kod, ad))
            seri = pd.concat(parcalar)
            tablolar.append(seri[~seri.index.duplicated(keep="last")])
        df = pd.concat(tablolar, axis=1).sort_index()
    except Exception as hata:
        log.warning("EVDS verisi alınamadı: %s", hata)
        return cache.oku("evds", "makro")

    cache.yaz(df, "evds", "makro")
    return df


def evds_parcalari(baslangic, bitis, yil: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """[baslangic, bitis] aralığını en fazla `yil` yıllık, çakışmayan parçalara böler."""
    bas, bitis = pd.Timestamp(baslangic), pd.Timestamp(bitis)
    parcalar = []
    while bas <= bitis:
        son = min(bas + pd.DateOffset(years=yil) - pd.Timedelta(days=1), bitis)
        parcalar.append((bas, son))
        bas = son + pd.Timedelta(days=1)
    return parcalar


def _evds_tablosunu_duzenle(ham: pd.DataFrame, kod: str, ad: str) -> pd.DataFrame:
    """EVDS çıktısını tarih indeksli tek sütunlu tabloya çevirir."""
    sutun = kod.replace(".", "_")
    tarih_metni = ham["Tarih"].astype(str)
    if tarih_metni.str.match(r"^\d{4}-\d{1,2}$").all():          # aylık: '2015-1'
        tarih = pd.to_datetime(tarih_metni, format="%Y-%m")
    else:                                                          # günlük: '01-01-2015'
        tarih = pd.to_datetime(tarih_metni, dayfirst=True)
    seri = pd.to_numeric(ham[sutun], errors="coerce")
    df = pd.DataFrame({ad: seri.values}, index=pd.DatetimeIndex(tarih, name="tarih")).dropna()
    if ad == "tufe":
        # Aylık TÜFE ertesi ayın 3'ünde açıklanır
        df["tufe_yayin_tarihi"] = df.index + pd.DateOffset(months=1, days=2)
    return df

