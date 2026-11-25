"""Performans metrikleri: toplam getiri, CAGR, volatilite, Sharpe, maksimum düşüş, kazanma oranı.

Girdi: günlük getiri serisi (strateji ya da portföy). Yıllıklandırma 252 işlem günüyle yapılır.
Sharpe oranında risksiz faiz olarak politika faizi kullanılır: Türkiye'de faiz %40'larda iken
risksiz faizi 0 saymak her stratejiyi olduğundan çok daha iyi gösterir.
"""

import numpy as np
import pandas as pd

YILLIK_GUN = 252


def sermaye_egrisi(getiri: pd.Series, baslangic: float = 1.0) -> pd.Series:
    """Günlük getirilerden birikimli sermaye eğrisi."""
    return baslangic * (1 + getiri.fillna(0)).cumprod()


def maksimum_dusus(egri: pd.Series) -> float:
    """Zirveden en büyük düşüş (negatif oran, ör. -0.35 = %35 düşüş)."""
    zirve = egri.cummax()
    return float((egri / zirve - 1).min())


def cagr(getiri: pd.Series) -> float:
    """Yıllık bileşik büyüme oranı."""
    getiri = getiri.dropna()
    if len(getiri) == 0:
        return np.nan
    toplam = (1 + getiri).prod()
    return float(toplam ** (YILLIK_GUN / len(getiri)) - 1)


def sharpe(getiri: pd.Series, risksiz_yillik: pd.Series | float = 0.0) -> float:
    """Yıllıklandırılmış Sharpe: (getiri - risksiz) ortalaması / standart sapma × √252."""
    getiri = getiri.dropna()
    if isinstance(risksiz_yillik, pd.Series):
        risksiz = risksiz_yillik.reindex(getiri.index).ffill().bfill().fillna(0) / YILLIK_GUN
    else:
        risksiz = risksiz_yillik / YILLIK_GUN
    fazla = getiri - risksiz
    if fazla.std() == 0 or len(fazla) < 2:
        return np.nan
    return float(fazla.mean() / fazla.std() * np.sqrt(YILLIK_GUN))


def islem_istatistikleri(pozisyon: pd.Series, getiri: pd.Series) -> tuple[int, float]:
    """İşlem sayısı ve kazanma oranı (girişten çıkışa toplam getirisi > 0 olan işlemlerin oranı).

    pozisyon: her günün aralığında tutulan pozisyon (0/1); getiri: aynı aralığın varlık getirisi.
    """
    acik = pozisyon.fillna(0) > 0
    if not acik.any():
        return 0, np.nan
    islem_no = (acik & ~acik.shift(1, fill_value=False)).cumsum()[acik]
    islem_getirisi = (1 + getiri[acik].fillna(0)).groupby(islem_no).prod() - 1
    return int(len(islem_getirisi)), float((islem_getirisi > 0).mean())


def ozet(getiri: pd.Series, risksiz_yillik: pd.Series | float = 0.0,
         pozisyon: pd.Series | None = None, varlik_getirisi: pd.Series | None = None,
         usdtry: pd.Series | None = None) -> pd.Series:
    """Bir stratejinin tüm metrikleri tek satırda."""
    getiri = getiri.dropna()
    egri = sermaye_egrisi(getiri)
    sonuc = {
        "toplam_getiri": float(egri.iloc[-1] - 1) if len(egri) else np.nan,
        "cagr": cagr(getiri),
        "yillik_volatilite": float(getiri.std() * np.sqrt(YILLIK_GUN)),
        "sharpe": sharpe(getiri, risksiz_yillik),
        "maks_dusus": maksimum_dusus(egri) if len(egri) else np.nan,
    }
    if usdtry is not None and len(egri):
        kur = usdtry.reindex(egri.index).ffill().bfill()
        usd_egri = egri / kur * kur.iloc[0]
        yil = len(egri) / YILLIK_GUN
        sonuc["cagr_usd"] = float(usd_egri.iloc[-1] ** (1 / yil) - 1)
        sonuc["maks_dusus_usd"] = maksimum_dusus(usd_egri)
    if pozisyon is not None and varlik_getirisi is not None:
        poz = pozisyon.reindex(getiri.index)
        sayi, kazanma = islem_istatistikleri(poz, varlik_getirisi.reindex(getiri.index))
        sonuc["islem_sayisi"] = sayi
        sonuc["kazanma_orani"] = kazanma
        sonuc["piyasada_kalma"] = float((poz.fillna(0) > 0).mean())
    return pd.Series(sonuc)
