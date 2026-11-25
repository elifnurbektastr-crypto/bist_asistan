"""Model değerlendirme: doğruluk, AUC, baseline karşılaştırması, getiri farkı, aşırı öğrenme alarmı.

Doğruluk tek başına yanıltıcıdır: TL'de "hep yükselir" bile %52'yi tutturur.
Bu yüzden asıl bakılan şey, modelin sıraladığı hisselerin gerçekten farklı getiri verip vermediğidir.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

ASIRI_OGRENME_ESIGI = 0.65


def _dilim_farki(grup: pd.DataFrame, dilim: float = 0.2) -> float:
    """Aynı gün içinde olasılığı en yüksek %20 ile en düşük %20 hissenin ortalama getiri farkı."""
    if len(grup) < 10:
        return np.nan
    ust = grup["olasilik"].quantile(1 - dilim)
    alt = grup["olasilik"].quantile(dilim)
    return grup.loc[grup["olasilik"] >= ust, "getiri"].mean() - grup.loc[grup["olasilik"] <= alt, "getiri"].mean()


def metrikler(tahmin: pd.DataFrame) -> pd.Series:
    """Tek bir model ve dönem için özet metrikler."""
    y, p = tahmin["gercek"].astype(int), tahmin["olasilik"].clip(1e-6, 1 - 1e-6)
    sinyal = p > 0.5
    tek_sinif = y.nunique() < 2 or p.nunique() < 2
    gunluk_fark = tahmin.groupby(level="tarih").apply(_dilim_farki).dropna()
    return pd.Series({
        "dogruluk": (sinyal == y.astype(bool)).mean(),
        "auc": np.nan if tek_sinif else roc_auc_score(y, p),
        "log_kayip": log_loss(y, p, labels=[0, 1]),
        "brier": brier_score_loss(y, p),
        "al_sinyali_orani": sinyal.mean(),
        # sinyal=al dediği günlerin ortalama 5g getirisi ile tüm günlerin ortalaması arasındaki fark
        "al_getiri_farki": tahmin.loc[sinyal.values, "getiri"].mean() - tahmin["getiri"].mean() if sinyal.any() else np.nan,
        "ust_alt_dilim_farki": gunluk_fark.mean(),
        "satir": len(tahmin),
    })


def ozet_tablo(tahminler: pd.DataFrame) -> pd.DataFrame:
    """Tüm test yılları birlikte, model başına metrikler."""
    return tahminler.groupby("model").apply(metrikler).sort_values("auc", ascending=False)


def yillik_tablo(tahminler: pd.DataFrame, metrik: str = "dogruluk") -> pd.DataFrame:
    """Model × yıl tablosu (sonuç yıllara göre istikrarlı mı?)."""
    return tahminler.groupby(["model", "yil"]).apply(lambda g: metrikler(g)[metrik]).unstack("yil")


def esik_analizi(tahmin: pd.DataFrame, esikler=(0.5, 0.52, 0.54, 0.56, 0.58, 0.6)) -> pd.DataFrame:
    """Model sadece 'emin' olduğunda sinyal üretirse: kapsama ve isabet nasıl değişir?"""
    satirlar = []
    for e in esikler:
        secili = tahmin[tahmin["olasilik"] > e]
        satirlar.append({
            "esik": e, "kapsama": len(secili) / len(tahmin),
            "isabet": secili["gercek"].mean() if len(secili) else np.nan,
            "ort_getiri": secili["getiri"].mean() if len(secili) else np.nan,
        })
    return pd.DataFrame(satirlar).set_index("esik")


def asiri_ogrenme_alarmi(ozet: pd.DataFrame) -> list[str]:
    """Doğruluğu %65'i aşan modeller: başarı değil, büyük ihtimalle veri sızıntısı."""
    return ozet.index[ozet["dogruluk"] > ASIRI_OGRENME_ESIGI].tolist()


def vol_metrikleri(tahmin: pd.DataFrame) -> pd.Series:
    """Volatilite tahmini: hata, açıklanan varyans (R²) ve sıralama korelasyonu."""
    y, p = tahmin["gercek"], tahmin["tahmin"]
    return pd.Series({
        "ort_mutlak_hata": (y - p).abs().mean(),
        "r2": 1 - ((y - p) ** 2).sum() / ((y - y.mean()) ** 2).sum(),
        "spearman": y.corr(p, method="spearman"),
        "satir": len(tahmin),
    })
