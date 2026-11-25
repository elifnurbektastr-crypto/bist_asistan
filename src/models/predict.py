"""Güncel tahmin: tüm geçmişle eğitilmiş modelle son işlem gününün tahmini.

Ajanın `model_tahmini(sembol)` aracı bu modülü kullanacak. Tahminle birlikte modelin
walk-forward'daki geçmiş başarısı da döner, böylece kullanıcı tahmine ne kadar
güvenebileceğini görür.
"""

import numpy as np
import pandas as pd

from src.data import cache
from src.features.indicators import OZELLIKLER
from src.models import evaluate, train

VARSAYILAN_MODEL = "lightgbm_ince_ayar"
GUVEN_ESIGI = 0.60   # bu olasılığın üstü "güçlü sinyal" sayılır (eşik analizi, Deney 4)


def guncel_tahminler(tablo: pd.DataFrame, model: str = VARSAYILAN_MODEL) -> pd.DataFrame:
    """Hedefi bilinen tüm geçmişle eğitip son günün özelliklerinden tahmin üretir."""
    son_tarih = tablo.index.get_level_values("tarih").max()
    bilinen = tablo["hedef_yon"].notna() & tablo["getiri_60"].notna()
    egitim = tablo[bilinen & (tablo["hedef_bitis_yon"] <= son_tarih)]
    son_gun = tablo.xs(son_tarih, level="tarih", drop_level=False)
    son_gun = son_gun[son_gun["getiri_60"].notna()]
    olasilik = train.MODELLER[model](egitim, son_gun, "hedef_yon")

    vol_model = train.lgb.LGBMRegressor(**train.LGBM_AYARLARI)
    vol_egitim = tablo[tablo["hedef_vol_20"].gt(0) & tablo["hedef_bitis_vol"].le(son_tarih)]
    vol_model.fit(vol_egitim[OZELLIKLER], np.log(vol_egitim["hedef_vol_20"]))

    sonuc = pd.DataFrame({
        "yukselis_olasiligi": olasilik,
        "sinyal": np.where(olasilik > GUVEN_ESIGI, "güçlü al", np.where(olasilik > 0.5, "zayıf al", "al değil")),
        "beklenen_vol_20": np.exp(vol_model.predict(son_gun[OZELLIKLER])),
    }, index=son_gun.index.get_level_values("kod"))
    sonuc.attrs["tarih"] = son_tarih.date()
    return sonuc.sort_values("yukselis_olasiligi", ascending=False)


def gecmis_basari(kod: str | None = None, model: str = VARSAYILAN_MODEL) -> pd.Series:
    """Modelin walk-forward (görülmemiş veri) başarısı; kod verilirse o hisse için."""
    tahminler = cache.oku("tahminler", "model")
    if tahminler is None:
        return pd.Series(dtype=float)
    t = tahminler[tahminler["model"] == model]
    if kod:
        t = t[t.index.get_level_values("kod") == kod.upper()]
    m = evaluate.metrikler(t)
    guclu = t[t["olasilik"] > GUVEN_ESIGI]
    m["guclu_sinyal_isabeti"] = guclu["gercek"].mean() if len(guclu) else np.nan
    m["guclu_sinyal_sayisi"] = len(guclu)
    return m
