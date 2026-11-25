"""Stratejiler: her biri t günü kapanışında bilinen bilgiyle 0/1 hedef pozisyon üretir.

Sinyal t kapanışında oluşur; motor (engine.py) bu pozisyonu t+1 açılışında uygular.
Hiçbir strateji t'den sonraki veriyi kullanmaz.
"""

import numpy as np
import pandas as pd

from src.features.indicators import HEDEF_UFKU, rsi


def al_ve_tut(df: pd.DataFrame) -> pd.Series:
    """Karşılaştırma ölçütü: ilk gün al, hiç satma."""
    return pd.Series(1.0, index=df.index)


def ma_kesisim(df: pd.DataFrame, kisa: int = 20, uzun: int = 50) -> pd.Series:
    """Kısa ortalama uzun ortalamanın üstündeyken pozisyonda kal (trend takibi)."""
    k = df["duz_kapanis"]
    kisa_ma, uzun_ma = k.rolling(kisa).mean(), k.rolling(uzun).mean()
    return (kisa_ma > uzun_ma).astype(float).where(uzun_ma.notna(), 0.0)


def rsi_stratejisi(df: pd.DataFrame, alt: float = 30, ust: float = 70, pencere: int = 14) -> pd.Series:
    """RSI alt eşiğin altına inince al, üst eşiğin üstüne çıkınca sat (ortalamaya dönüş)."""
    r = rsi(df["duz_kapanis"], pencere)
    durum = pd.Series(np.nan, index=df.index)
    durum[r < alt] = 1.0
    durum[r > ust] = 0.0
    return durum.ffill().fillna(0.0)


def ml_sinyali(df: pd.DataFrame, olasilik: pd.Series, esik: float = 0.60,
               ufuk: int = HEDEF_UFKU) -> pd.Series:
    """Model olasılığı eşiği aşınca al ve `ufuk` gün tut (model 5 günlük getiriyi tahmin ediyor).

    Karar sadece her `ufuk` günde bir verilir; böylece pozisyon her gün değişip
    gereksiz komisyon ödenmez. Tahmini olmayan günlerde pozisyon yoktur.
    """
    olasilik = olasilik.reindex(df.index)
    karar_gunu = pd.Series(np.arange(len(df)) % ufuk == 0, index=df.index)
    karar = (olasilik > esik).astype(float).where(olasilik.notna(), 0.0)
    return karar.where(karar_gunu).ffill().fillna(0.0)


STRATEJILER = {
    "al_ve_tut": al_ve_tut,
    "ma_kesisim": ma_kesisim,
    "rsi": rsi_stratejisi,
}
