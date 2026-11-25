"""Özellikler (features) ve hedef değişkenler.

Kural: t günündeki her özellik yalnızca t günü kapanışında bilinen bilgiyi kullanır.
Hedefler ise geleceğe bakar ve yalnızca eğitim/değerlendirme için kullanılır.
Tüm özellikler oran/yüzde cinsindendir, böylece farklı fiyat seviyesindeki hisseler
tek bir ortak modelde birlikte kullanılabilir.
"""

import numpy as np
import pandas as pd

HEDEF_UFKU = 5          # gün: yön hedefi
VOL_UFKU = 20           # gün: volatilite hedefi
YILLIK_GUN = 252

# Hisseye özgü özellikler: modelde varsayılan olarak bunlar kullanılır.
HISSE_OZELLIKLERI = [
    "getiri_1", "getiri_5", "getiri_20", "getiri_60",
    "volatilite_20", "volatilite_60", "vol_orani",
    "ma20_uzaklik", "ma50_uzaklik", "ma20_ma50",
    "rsi_14", "hacim_orani", "gun_ici_aralik", "goreli_getiri_20",
]
# Piyasa geneli özellikler: aynı gün tüm hisselerde aynı değer. Deney 1-2'de modeli
# "piyasa zamanlamasına" itti ve rejim değişiminde (2022) ters tahmin ürettiği için
# varsayılan setten çıkarıldı. Hesaplanmaya devam ediyor (deneylerde kullanılabilir).
PIYASA_OZELLIKLERI = [
    "endeks_getiri_5", "endeks_getiri_20", "kur_getiri_5", "kur_getiri_20",
    "yillik_enflasyon", "politika_faizi", "reel_faiz",
]
TUM_OZELLIKLER = HISSE_OZELLIKLERI + PIYASA_OZELLIKLERI
OZELLIKLER = HISSE_OZELLIKLERI


def rsi(kapanis: pd.Series, pencere: int = 14) -> pd.Series:
    """Wilder RSI (0-100). Üssel ortalama sadece geçmişi kullanır."""
    fark = kapanis.diff()
    kazanc = fark.clip(lower=0).ewm(alpha=1 / pencere, adjust=False, min_periods=pencere).mean()
    kayip = (-fark.clip(upper=0)).ewm(alpha=1 / pencere, adjust=False, min_periods=pencere).mean()
    rs = kazanc / kayip
    return 100 - 100 / (1 + rs)


def hisse_ozellikleri(df: pd.DataFrame) -> pd.DataFrame:
    """Tek hissenin fiyat tablosundan teknik özellikleri hesaplar (düzeltilmiş fiyatla)."""
    k = df["duz_kapanis"]
    g = k.pct_change()
    ma20, ma50 = k.rolling(20).mean(), k.rolling(50).mean()
    oz = pd.DataFrame(index=df.index)
    for n in [1, 5, 20, 60]:
        oz[f"getiri_{n}"] = k / k.shift(n) - 1
    oz["volatilite_20"] = g.rolling(20).std() * np.sqrt(YILLIK_GUN)
    oz["volatilite_60"] = g.rolling(60).std() * np.sqrt(YILLIK_GUN)
    oz["vol_orani"] = oz["volatilite_20"] / oz["volatilite_60"]
    oz["ma20_uzaklik"] = k / ma20 - 1
    oz["ma50_uzaklik"] = k / ma50 - 1
    oz["ma20_ma50"] = ma20 / ma50 - 1
    oz["rsi_14"] = rsi(k)
    # Hacim TL cinsinden (hacim × fiyat): bölünmelerden etkilenmez
    tl_hacim = df["hacim"] * df["kapanis"]
    oz["hacim_orani"] = np.log(tl_hacim.rolling(5).mean() / tl_hacim.rolling(60).mean())
    oz["gun_ici_aralik"] = (df["duz_yuksek"] - df["duz_dusuk"]) / df["duz_kapanis"]
    return oz


def hedefler(df: pd.DataFrame) -> pd.DataFrame:
    """Gelecekteki getiriler: yalnızca eğitim ve değerlendirme içindir.

    Sinyal t kapanışında üretilir, t+1 açılışında işleme girilir, t+1+UFUK açılışında çıkılır.
    hedef_bitis_*: hedefin dayandığı son gün. Walk-forward'da bu gün test döneminin
    içine düşen eğitim satırları atılır (purging), yoksa eğitim test fiyatlarını "görür".
    """
    a = df["duz_acilis"]
    giris, cikis = a.shift(-1), a.shift(-1 - HEDEF_UFKU)
    h = pd.DataFrame(index=df.index)
    h["hedef_getiri"] = cikis / giris - 1
    h["hedef_yon"] = (h["hedef_getiri"] > 0).astype(float).where(h["hedef_getiri"].notna())
    g = df["duz_kapanis"].pct_change()
    # t+1 ... t+20 günlerinin getirilerinin standart sapması (gelecek volatilite)
    h["hedef_vol_20"] = g[::-1].rolling(VOL_UFKU).std()[::-1].shift(-1) * np.sqrt(YILLIK_GUN)
    tarihler = pd.Series(df.index, index=df.index)
    h["hedef_bitis_yon"] = tarihler.shift(-(1 + HEDEF_UFKU))
    h["hedef_bitis_vol"] = tarihler.shift(-VOL_UFKU)
    return h


def piyasa_ozellikleri(endeks: pd.DataFrame, kur: pd.DataFrame | None) -> pd.DataFrame:
    """Endeks ve kur kaynaklı, tüm hisseler için ortak özellikler."""
    k = endeks["duz_kapanis"]
    oz = pd.DataFrame(index=endeks.index)
    oz["endeks_getiri_5"] = k / k.shift(5) - 1
    oz["endeks_getiri_20"] = k / k.shift(20) - 1
    if kur is not None:
        # Kur hafta sonu da işlem görür; borsa günlerine son bilinen değerle hizalanır
        kk = kur["kapanis"].reindex(endeks.index, method="ffill")
        oz["kur_getiri_5"] = kk / kk.shift(5) - 1
        oz["kur_getiri_20"] = kk / kk.shift(20) - 1
    return oz


def makro_ozellikleri(makro: pd.DataFrame | None, takvim: pd.DatetimeIndex) -> pd.DataFrame:
    """Yıllık enflasyon ve faizi işlem günlerine hizalar — yayın tarihine göre.

    Ekim TÜFE'si 3 Kasım'da açıklanır: Kasım'ın ilk iki günü hâlâ Eylül verisi kullanılır.
    Faiz günlük yayımlanır ama gün sonunda kesinleştiği için bir gün gecikmeli kullanılır.
    """
    oz = pd.DataFrame(index=takvim)
    if makro is None:
        return oz
    tufe = makro[["tufe", "tufe_yayin_tarihi"]].dropna()
    yillik = (tufe["tufe"] / tufe["tufe"].shift(12) - 1).dropna()
    yayin = pd.Series(yillik.values, index=pd.DatetimeIndex(tufe.loc[yillik.index, "tufe_yayin_tarihi"]))
    oz["yillik_enflasyon"] = yayin.sort_index().reindex(takvim.union(yayin.index)).ffill().reindex(takvim)
    faiz = makro["politika_faizi"].dropna() / 100
    oz["politika_faizi"] = faiz.reindex(takvim.union(faiz.index)).ffill().shift(1).reindex(takvim)
    oz["reel_faiz"] = oz["politika_faizi"] - oz["yillik_enflasyon"]
    return oz


def veri_seti_olustur(veri: dict[str, pd.DataFrame], endeks: pd.DataFrame,
                      kur: pd.DataFrame | None = None, makro: pd.DataFrame | None = None) -> pd.DataFrame:
    """Tüm hisseler için (tarih, kod) satırlı uzun formatta özellik + hedef tablosu."""
    piyasa = piyasa_ozellikleri(endeks, kur)
    makro_oz = makro_ozellikleri(makro, endeks.index)
    parcalar = []
    for sembol, df in veri.items():
        oz = hisse_ozellikleri(df).join(hedefler(df))
        oz = oz.join(piyasa, how="left").join(makro_oz, how="left")
        oz["goreli_getiri_20"] = oz["getiri_20"] - oz["endeks_getiri_20"]
        oz["kod"] = sembol.replace(".IS", "")
        parcalar.append(oz)
    tablo = pd.concat(parcalar)
    tablo.index.name = "tarih"
    tablo = tablo.reset_index().set_index(["tarih", "kod"]).sort_index()
    eksik = [s for s in TUM_OZELLIKLER if s not in tablo]
    for s in eksik:   # kur/makro yoksa sütun NaN olarak kalır (LightGBM NaN'ı işler)
        tablo[s] = np.nan
    return tablo
