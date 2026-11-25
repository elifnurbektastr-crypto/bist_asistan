"""Temettü modülü: geçmiş ödemeler, özet tablo, yaklaşan hak kullanım tarihleri, filtreleme.

Tutarlar BRÜT ve hisse başınadır (stopaj düşülmemiştir).
Yaklaşan tarihler yalnızca yfinance'ten gelir ve DOĞRULANMAMIŞTIR (resmi kaynak KAP'tır).
"""

import logging
import time

import pandas as pd
import yfinance as yf

from src import config
from src.data import cache

log = logging.getLogger(__name__)

YAKLASAN_KAYNAK = "yfinance (doğrulanmadı)"


def temettu_gecmisi(df: pd.DataFrame) -> pd.DataFrame:
    """Bir hissenin geçmiş temettü ödemeleri.

    tl          : o tarihte hisse başına ödenen brüt TL (o günkü hisse sayısıyla)
    tl_bugunku  : aynı ödeme, bugünkü hisse sayısı bazında (bölünmeler sonrası)
    verim       : tl / hak kullanımından önceki günün ham kapanışı
    """
    onceki_kapanis = df["kapanis"].shift(1)
    secili = df["temettu"] > 0
    return pd.DataFrame({
        "tl": df.loc[secili, "temettu"],
        "tl_bugunku": df.loc[secili, "temettu_duz"],
        "onceki_kapanis": onceki_kapanis[secili],
        "verim": df.loc[secili, "temettu"] / onceki_kapanis[secili],
    })


def kesintisiz_yil(tarihler: pd.DatetimeIndex, bugun: pd.Timestamp) -> int:
    """Geriye doğru kaç takvim yılı üst üste temettü ödendiğini sayar.

    Bu yıl henüz ödeme yoksa sayım geçen yıldan başlar (yıl bitmeden 'kesildi' denmez).
    """
    yillar = set(pd.DatetimeIndex(tarihler).year)
    yil = bugun.year if bugun.year in yillar else bugun.year - 1
    sayi = 0
    while yil in yillar:
        sayi += 1
        yil -= 1
    return sayi


def temettu_ozeti(veri: dict[str, pd.DataFrame], bugun: pd.Timestamp | None = None) -> pd.DataFrame:
    """Hisse başına temettü özet tablosu (filtreleme ekranının ana tablosu).

    son12ay_verim: son 365 günde ödenen temettülerin (bugünkü hisse bazında) son fiyata oranı.
    Bölünme bazı eşitlenmezse bedelsiz sonrası verim olduğundan yüksek görünür.
    """
    bugun = (bugun or pd.Timestamp.today()).normalize()
    satirlar = []
    for sembol, df in veri.items():
        if df.empty:
            continue
        gecmis = temettu_gecmisi(df)
        son12 = gecmis[gecmis.index > bugun - pd.Timedelta(days=365)]
        son_fiyat = df["kapanis"].iloc[-1]
        satirlar.append({
            "kod": sembol.replace(".IS", ""),
            "son_fiyat": son_fiyat,
            "son_temettu_tarihi": gecmis.index.max().date() if len(gecmis) else None,
            "son_temettu_tl": gecmis["tl"].iloc[-1] if len(gecmis) else 0.0,
            "son12ay_tl": son12["tl_bugunku"].sum(),
            "son12ay_verim": son12["tl_bugunku"].sum() / son_fiyat if son_fiyat else 0.0,
            "son12ay_odeme_sayisi": len(son12),
            "kesintisiz_yil": kesintisiz_yil(gecmis.index, bugun),
        })
    return pd.DataFrame(satirlar).set_index("kod") if satirlar else pd.DataFrame()


def yaklasan_durumu(tarih, bugun: pd.Timestamp) -> tuple[str, int | None]:
    """yfinance'ten gelen hak kullanım tarihini yorumlar: (durum, kalan gün)."""
    if tarih is None or pd.isna(tarih):
        return "bilgi yok", None
    kalan = (pd.Timestamp(tarih).normalize() - bugun.normalize()).days
    if kalan < 0:
        return "tarih geçmiş (güncel bilgi yok)", kalan
    return "yaklaşan", kalan


def yaklasan_temettuler(semboller: list[str], yenile: bool = False,
                        bugun: pd.Timestamp | None = None) -> pd.DataFrame:
    """Her hisse için yfinance'in bildirdiği bir sonraki hak kullanım tarihini döner.

    Uyarı: yfinance bazı hisselerde eski tarih gösteriyor, tutarı da vermiyor.
    Sonuç günde bir kez çekilip önbelleğe alınır.
    """
    bugun = (bugun or pd.Timestamp.today()).normalize()
    if not yenile:
        onbellek = cache.oku("yaklasan", "temettu")
        zaman = cache.guncelleme_tarihi("yaklasan", "temettu")
        if onbellek is not None and zaman is not None and \
                zaman.tz_convert(config.SAAT_DILIMI).date() == pd.Timestamp.now(tz=config.SAAT_DILIMI).date():
            return onbellek

    satirlar = []
    for kod in semboller:
        sembol = config.yf_sembol(kod)
        tarih = None
        try:
            takvim = yf.Ticker(sembol).calendar or {}
            tarih = takvim.get("Ex-Dividend Date")
        except Exception as hata:
            log.warning("%s yaklaşan temettü alınamadı: %s", sembol, hata)
        durum, kalan = yaklasan_durumu(tarih, bugun)
        satirlar.append({
            "kod": sembol.replace(".IS", ""),
            "hak_kullanim_tarihi": pd.Timestamp(tarih) if tarih is not None else pd.NaT,
            "kalan_gun": kalan,
            "durum": durum,
            "kaynak": YAKLASAN_KAYNAK,
        })
        time.sleep(0.5)  # Yahoo'yu yormamak için
    df = pd.DataFrame(satirlar).set_index("kod")
    cache.yaz(df, "yaklasan", "temettu")
    return df


def filtrele(tablo: pd.DataFrame, min_verim: float | None = None, min_tl: float | None = None,
             min_kesintisiz_yil: int | None = None, gun_icinde: int | None = None,
             sektor: list[str] | None = None) -> pd.DataFrame:
    """Temettü tablosunu filtreler.

    tablo: temettu_ozeti çıktısı (gun_icinde için yaklasan_temettuler ile birleştirilmiş olmalı)
    min_verim: ör. 0.05 = son 12 ayda en az %5 verim
    min_tl: son 12 ayda hisse başına en az bu kadar TL
    gun_icinde: hak kullanım tarihi önümüzdeki N gün içinde olanlar
    """
    maske = pd.Series(True, index=tablo.index)
    if min_verim is not None:
        maske &= tablo["son12ay_verim"] >= min_verim
    if min_tl is not None:
        maske &= tablo["son12ay_tl"] >= min_tl
    if min_kesintisiz_yil is not None:
        maske &= tablo["kesintisiz_yil"] >= min_kesintisiz_yil
    if gun_icinde is not None:
        maske &= (tablo["durum"] == "yaklaşan") & (tablo["kalan_gun"] <= gun_icinde)
    if sektor:
        maske &= tablo["sektor"].isin(sektor)
    return tablo[maske]
