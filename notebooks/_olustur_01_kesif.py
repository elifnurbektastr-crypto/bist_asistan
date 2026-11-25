"""01_kesif.ipynb dosyasını üretir (notebook'u elle değil, kodla oluşturuyoruz ki gözden geçirmesi kolay olsun).

Kullanım: python notebooks/_olustur_01_kesif.py  ->  ardından notebook'u çalıştırın.
"""

from pathlib import Path

import nbformat as nbf

h = []
md = lambda s: h.append(nbf.v4.new_markdown_cell(s.strip()))
kod = lambda s: h.append(nbf.v4.new_code_cell(s.strip()))

md("""
# 01 · Keşifsel Veri Analizi (BIST 100)

Bu notebook **sadece önbellekteki veriyi okur** (internete bağlanmaz). Önce veriyi güncelleyin:
`python -m src.data.guncelle`

Sorular:
1. Veri ne kadar eksiksiz? Hangi hisselerin geçmişi kısa?
2. Ham ve düzeltilmiş fiyat neden farklı, düzeltme doğru mu?
3. TL bazında ve USD bazında BIST getirisi ne kadar farklı?
4. Getiriler normal dağılıyor mu?
5. Temettü verimi en yüksek hisseler hangileri?
6. Enflasyon ve faiz nasıl seyretti?
""")

kod("""
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from src import config
from src.data import cache, dividends, quality
from src.data.fetch import elle_duzeltmeleri_uygula, elle_duzeltmeler, tatil_satirlarini_at

pd.set_option("display.width", 160)
pd.set_option("display.float_format", "{:,.3f}".format)

# Grafik stili: açık zemin, sade eksenler, sabit renk sırası
MAVI, TURUNCU = "#2a78d6", "#eb6834"
plt.rcParams.update({
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb", "axes.edgecolor": "#c9c8c3",
    "axes.labelcolor": "#52514e", "xtick.color": "#52514e", "ytick.color": "#52514e",
    "axes.grid": True, "grid.color": "#ebeae6", "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 2,
    "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold", "axes.axisbelow": True,
})

def oku(sembol, duzelt=True):
    # Önbellekten okur; tatil satırlarını atar ve referans/duzeltmeler.csv'yi uygular
    df = cache.oku(sembol)
    if df is None:
        return None
    df = tatil_satirlarini_at(df)
    return elle_duzeltmeleri_uygula(df, elle_duzeltmeler(sembol)) if duzelt else df

hisseler = config.hisse_evreni("bist100")
veri = {h: df for h in hisseler if (df := oku(config.yf_sembol(h))) is not None}
endeks, kur = oku(config.ENDEKS), oku(config.USDTRY)
makro = cache.oku("evds", "makro")
print(f"Önbellekte {len(veri)}/{len(hisseler)} hisse | XU100: {endeks is not None} | USD/TRY: {kur is not None} | EVDS: {makro is not None}")
""")

md("""
## 1. Kapsam ve veri kalitesi
2015'ten sonra halka arz olan hisselerin geçmişi kısadır. Bu, ML'de örnek sayısını ve walk-forward pencerelerini etkiler.
""")

kod("""
takvim = endeks.index if endeks is not None else None
kalite = quality.kalite_tablosu(veri, takvim)
kalite["yil"] = (pd.to_datetime(kalite["son_tarih"]) - pd.to_datetime(kalite["ilk_tarih"])).dt.days / 365.25
print("Geçmişi 5 yıldan kısa olan hisseler:")
display(kalite[kalite["yil"] < 5][["ilk_tarih", "satir", "yil"]].sort_values("yil"))
print("\\nÖzet:")
display(kalite[["satir", "nan", "yinelenen_tarih", "sifir_hacim", "ohlc_tutarsiz", "limit_asimi", "bolunme", "temettu"]].describe().loc[["mean", "min", "max"]])
""")

md("""
### ±%10 limitini aşan günler
BIST'te günlük fiyat limiti ±%10. Aşan günlerin bir kısmı gerçek olaydır (darbe girişimi 2016-07-18, deprem sonrası açılış 2023-02-15, COVID 2020-03),
bir kısmı ise Yahoo'nun düzeltmediği **bedelli sermaye artırımlarıdır** (sahte düşüş). Hangi tarihlerin birden çok hissede görüldüğüne bakalım:
""")

kod("""
tarihler = pd.Series([t for r in kalite["limit_asimi_tarihleri"] for t in r]).value_counts()
print("En çok hissede aynı anda görülen limit aşımları (piyasa geneli olay):")
display(tarihler.head(8).rename("hisse_sayisi").to_frame())
print(f"Tek hissede görülen limit aşımı: {(tarihler == 1).sum()} gün (şirkete özel olay ya da veri sorunu)")
""")

md("""
## 2. Ham ve düzeltilmiş fiyat
FROTO 2025-05-07'de 1'e 10 bedelsiz yaptı. Ham fiyat o gün ~%90 "düşer", ama yatırımcının serveti değişmez: hisse sayısı 10 katına çıkar.
Getiri hesabında ham fiyat kullanılırsa sahte bir -%90 oluşur. Bu yüzden iki seriyi ayrı tutuyoruz.
""")

kod("""
froto = veri["FROTO"].loc["2024-06":"2025-12"]
fig, eks = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
eks[0].plot(froto.index, froto["kapanis"], color=MAVI)
eks[0].set_title("FROTO · ham kapanış (TL) — grafikte gösterilen")
eks[1].plot(froto.index, froto["duz_kapanis"], color=MAVI)
eks[1].set_title("FROTO · düzeltilmiş kapanış (TL) — getiri hesabında kullanılan")
for e in eks:
    e.axvline(pd.Timestamp("2025-05-07"), color="#8a8984", linestyle="--", linewidth=1)
eks[0].annotate("1:10 bedelsiz", (pd.Timestamp("2025-05-07"), froto["kapanis"].max() * 0.9),
                xytext=(8, 0), textcoords="offset points", color="#52514e")
plt.tight_layout(); plt.show()

print("Bölünme hesabının doğrulanması (sapma ≈ 1 olmalı):")
kontrol = pd.concat({h: quality.bolunme_kontrolu(df) for h, df in veri.items()})
print(f"{len(kontrol)} bölünme, sapma min={kontrol['sapma'].min():.3f} max={kontrol['sapma'].max():.3f}")
""")

md("""
### Yahoo'nun kaçırdığı sermaye artırımları
Bazı bedelsiz/bedelli artırımlar Yahoo'da hiç kayıtlı değil ya da yanlış oranla kayıtlı. Sonuç: düzeltilmiş seride gerçekte yaşanmamış
"-%91 çöküşler". Bunları %35'ten büyük günlük hareketlerle tespit edip `referans/duzeltmeler.csv` dosyasına yazdık.
Oranlar şimdilik **fiyattan tahmin**; KAP duyurularından doğrulanacak.
""")

kod("""
ham_veri = {h: oku(config.yf_sembol(h), duzelt=False) for h in veri}
once = pd.concat({h: quality.supheli_sicramalar(df) for h, df in ham_veri.items()})
sonra = pd.concat({h: quality.supheli_sicramalar(df) for h, df in veri.items()}) if any(
    len(quality.supheli_sicramalar(df)) for df in veri.values()) else pd.DataFrame()
print(f"Düzeltme öncesi şüpheli gün: {len(once)} ({once.index.get_level_values(0).nunique()} hisse) | sonrası: {len(sonra)}")
display(pd.read_csv(config.REFERANS_DIZINI / "duzeltmeler.csv", comment="#"))

ccola_once, ccola_sonra = ham_veri["CCOLA"].loc["2024-05":"2024-11"], veri["CCOLA"].loc["2024-05":"2024-11"]
fig, ax = plt.subplots(figsize=(10, 3.8))
ax.plot(ccola_once.index, ccola_once["duz_kapanis"] / ccola_once["duz_kapanis"].iloc[0] * 100, color=TURUNCU, label="Yahoo'dan geldiği gibi")
ax.plot(ccola_sonra.index, ccola_sonra["duz_kapanis"] / ccola_sonra["duz_kapanis"].iloc[0] * 100, color=MAVI, label="Elle düzeltme sonrası")
ax.set_title("CCOLA · düzeltilmiş fiyat (başlangıç = 100)"); ax.legend(frameon=False, loc="lower left")
plt.tight_layout(); plt.show()
""")

md("""
## 3. TL ve USD bazında getiri
Yüksek enflasyonlu bir ülkede TL getirisi yanıltıcı olabilir. Aynı endeksi USD'ye çevirip 100'den başlatarak karşılaştırıyoruz (tek eksen, ortak baz).
""")

kod("""
if endeks is None or kur is None:
    print("XU100 ya da USD/TRY önbellekte yok; bu bölüm atlandı. `python -m src.data.guncelle` ile tekrar deneyin.")
else:
    ortak = endeks.index.intersection(kur.index)
    tl = endeks.loc[ortak, "duz_kapanis"]
    usd = tl / kur.loc[ortak, "kapanis"]
    tl_e, usd_e = tl / tl.iloc[0] * 100, usd / usd.iloc[0] * 100
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(tl_e.index, tl_e, color=MAVI, label="XU100 (TL)")
    ax.plot(usd_e.index, usd_e, color=TURUNCU, label="XU100 (USD)")
    ax.set_yscale("log"); ax.set_ylabel("Endeks (başlangıç = 100, log ölçek)")
    ax.set_title("BIST 100: TL ve USD bazında")
    for seri, renk in [(tl_e, MAVI), (usd_e, TURUNCU)]:
        ax.annotate(f"{seri.iloc[-1]:,.0f}", (seri.index[-1], seri.iloc[-1]), xytext=(4, 0),
                    textcoords="offset points", color="#0b0b0b", va="center")
    ax.legend(frameon=False, loc="upper left")
    plt.tight_layout(); plt.show()
    yil = (ortak[-1] - ortak[0]).days / 365.25
    print(f"Yıllık bileşik getiri ({ortak[0].date()} → {ortak[-1].date()}): "
          f"TL %{((tl.iloc[-1]/tl.iloc[0])**(1/yil)-1)*100:.1f} | USD %{((usd.iloc[-1]/usd.iloc[0])**(1/yil)-1)*100:.1f}")
""")

md("""
## 4. Günlük getirilerin dağılımı
Finansal getiriler normal dağılmaz: kuyruklar kalındır (aşırı günler beklenenden sık). Basıklık (kurtosis) 0'dan büyükse kuyruk kalındır.
""")

kod("""
getiri = pd.DataFrame({h: df["duz_kapanis"].pct_change() for h, df in veri.items()})
ozet = pd.DataFrame({
    "yillik_volatilite": getiri.std() * np.sqrt(252),
    "basiklik": getiri.kurt(),
    "carpiklik": getiri.skew(),
    "pozitif_gun_orani": (getiri > 0).sum() / getiri.notna().sum(),
}).sort_values("yillik_volatilite")
display(ozet.describe().loc[["mean", "min", "50%", "max"]])
print("\\n'Pozitif gün oranı' ML için önemli: 'hep yükselir' tahmini bu oranda doğru çıkar → baseline.")
""")

md("""
## 5. Temettü
Son 12 ay verimi = son 12 ayda ödenen temettüler (bugünkü hisse sayısı bazında) / son fiyat. Tutarlar brüttür.
""")

kod("""
ozet_t = dividends.temettu_ozeti(veri).sort_values("son12ay_verim", ascending=False)
ilk15 = ozet_t.head(15).iloc[::-1]
fig, ax = plt.subplots(figsize=(9, 6))
ax.barh(ilk15.index, ilk15["son12ay_verim"] * 100, color=MAVI, height=0.6)
for i, (v, tl) in enumerate(zip(ilk15["son12ay_verim"] * 100, ilk15["son12ay_tl"])):
    ax.annotate(f"%{v:.1f} · {tl:.2f} TL", (v, i), xytext=(4, 0), textcoords="offset points",
                va="center", color="#52514e", fontsize=9)
ax.set_xlabel("Son 12 ay temettü verimi (%)"); ax.grid(axis="y", visible=False)
ax.set_title("Temettü verimi en yüksek 15 hisse")
plt.tight_layout(); plt.show()
print("Filtre örneği: verim ≥ %5 ve en az 5 yıl kesintisiz")
display(dividends.filtrele(ozet_t, min_verim=0.05, min_kesintisiz_yil=5))
""")

md("""
## 6. Enflasyon ve politika faizi
İkisi de yüzde cinsinden, aynı eksende gösterilebilir. **Dikkat:** TÜFE ay bittikten sonra açıklanır; modelde `tufe_yayin_tarihi` kullanılmalı.
""")

kod("""
if makro is None:
    print("EVDS verisi yok (.env içinde EVDS_API_KEY tanımlayın).")
else:
    tufe = makro["tufe"].dropna()
    enflasyon = (tufe / tufe.shift(12) - 1).dropna() * 100
    faiz = makro["politika_faizi"].dropna()
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(enflasyon.index, enflasyon, color=MAVI, label="Yıllık TÜFE (%)")
    ax.plot(faiz.index, faiz, color=TURUNCU, label="Politika faizi / AOFM (%)")
    for seri, renk in [(enflasyon, MAVI), (faiz, TURUNCU)]:
        ax.annotate(f"%{seri.iloc[-1]:.1f}", (seri.index[-1], seri.iloc[-1]), xytext=(4, 0),
                    textcoords="offset points", color="#0b0b0b", va="center")
    ax.set_title("Enflasyon ve faiz"); ax.legend(frameon=False, loc="upper left")
    plt.tight_layout(); plt.show()
    reel = faiz.resample("MS").mean().reindex(enflasyon.index) - enflasyon
    print(f"Son ay reel faiz (faiz − yıllık enflasyon): {reel.dropna().iloc[-1]:.1f} puan")
""")

md("""
## Aşama 2 için çıkarımlar
- Getiri hesapları **düzeltilmiş** fiyatla yapılmalı; ham fiyat sadece gösterim içindir.
- **Baseline:** "hep yükselir" tahmininin doğruluğu pozitif gün oranına eşittir; model bunu geçmeli.
- Yahoo'nun kaçırdığı artırımlar elle düzeltildi (oranlar KAP'tan doğrulanmalı); yeni veride `supheli_sicrama` kontrolü takip edilmeli.
- Kalın kuyruklar (deprem sonrası açılış, COVID) gerçek olaylardır; silinmez ama modelde dikkate alınır.
- Kısa geçmişli hisseler walk-forward'da az pencere üretir; minimum geçmiş şartı konmalı.
- Makro veriler yayın tarihine göre gecikmeli kullanılmalı (look-ahead bias).
- TL getirisinin önemli kısmı enflasyondan geliyor: USD ve reel getiri ayrı raporlanmalı.
""")

nb = nbf.v4.new_notebook(cells=h, metadata={"kernelspec": {"name": "python3", "display_name": "Python 3"}})
nbf.write(nb, Path(__file__).with_name("01_kesif.ipynb"))
print("01_kesif.ipynb yazıldı")
