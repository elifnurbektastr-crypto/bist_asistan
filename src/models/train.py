"""Walk-forward eğitim: her yıl başında o güne kadarki veriyle eğit, o yılı tahmin et.

Rastgele bölme yok: model hiçbir zaman geleceğin verisiyle eğitilmez.
Purging: hedefi test dönemine taşan eğitim satırları atılır (5 günlük hedef 6 gün ileri bakar).
"""

import logging

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.features.indicators import OZELLIKLER

log = logging.getLogger(__name__)
TOHUM = 42
TEST_YILLARI = list(range(2019, 2027))

LGBM_AYARLARI = dict(
    n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=500,
    subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
    random_state=TOHUM, verbose=-1,
)


# ---------------------------------------------------------------------------
# Modeller: hepsi aynı arayüz -> egit_ve_tahmin(egitim, test) -> olasılık dizisi
# ---------------------------------------------------------------------------

def _hep_yukselir(egitim: pd.DataFrame, test: pd.DataFrame, hedef: str) -> np.ndarray:
    """Baseline: her zaman 'yükselir' der (olasılık = eğitimdeki pozitif oran, hep > 0.5)."""
    return np.full(len(test), max(egitim[hedef].mean(), 0.5 + 1e-9))


def _rastgele(egitim: pd.DataFrame, test: pd.DataFrame, hedef: str) -> np.ndarray:
    """Baseline: yazı-tura."""
    return np.random.default_rng(TOHUM).random(len(test))


def _sklearn(model):
    """sklearn modelini eksik değer doldurma ile birlikte saran yardımcı."""
    def egit_tahmin(egitim, test, hedef):
        boru = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), model)
        boru.fit(egitim[OZELLIKLER], egitim[hedef])
        return boru.predict_proba(test[OZELLIKLER])[:, 1]
    return egit_tahmin


def _lgbm_egit(egitim: pd.DataFrame, hedef: str, **ek) -> lgb.LGBMClassifier:
    """LightGBM sınıflandırıcıyı eğitir (NaN değerleri kendisi işler)."""
    model = lgb.LGBMClassifier(**{**LGBM_AYARLARI, **ek})
    model.fit(egitim[OZELLIKLER], egitim[hedef])
    return model


def _lightgbm(egitim, test, hedef):
    """1. basamak: tüm hisselerden tek ortak model."""
    return _lgbm_egit(egitim, hedef).predict_proba(test[OZELLIKLER])[:, 1]


def hisse_gruplari(egitim: pd.DataFrame, grup_sayisi: int = 5, son_gun: int = 500) -> dict[str, int]:
    """Hisseleri birlikte hareket etme derecesine göre gruplar.

    Sadece EĞİTİM verisinin son `son_gun` günü kullanılır (geleceği görmemek için).
    Uzaklık = 1 - günlük getiri korelasyonu; hiyerarşik kümeleme (ortalama bağlantı).
    """
    getiri = egitim["getiri_1"].unstack("kod")
    getiri = getiri.iloc[-son_gun:].dropna(axis=1, thresh=int(son_gun * 0.5))
    uzaklik = 1 - getiri.corr().fillna(0).values
    kume = AgglomerativeClustering(n_clusters=min(grup_sayisi, len(getiri.columns)),
                                   metric="precomputed", linkage="average")
    etiket = kume.fit_predict(uzaklik)
    return dict(zip(getiri.columns, etiket))


def _lightgbm_grup(egitim, test, hedef):
    """2. basamak: benzer hisse grupları için ayrı modeller; grubu olmayana ortak model."""
    gruplar = hisse_gruplari(egitim)
    ortak = _lgbm_egit(egitim, hedef)
    kod_egitim = egitim.index.get_level_values("kod").map(gruplar)
    kod_test = test.index.get_level_values("kod").map(gruplar)
    tahmin = ortak.predict_proba(test[OZELLIKLER])[:, 1]
    for g in set(gruplar.values()):
        e, t = egitim[kod_egitim == g], (kod_test == g)
        if len(e) < 20_000 or not t.any():
            continue   # küçük gruplarda ortak model kalır (aşırı öğrenmeyi önlemek için)
        tahmin[np.asarray(t)] = _lgbm_egit(e, hedef).predict_proba(test.loc[t, OZELLIKLER])[:, 1]
    return tahmin


def _lightgbm_ince_ayar(egitim, test, hedef, ek_agac: int = 40):
    """3. basamak: ortak modeli her hissenin kendi verisiyle birkaç ağaç daha eğitir.

    LightGBM 'init_model' ile kaldığı yerden devam eder: ortak model piyasanın genel
    davranışını öğrenmiştir, ek ağaçlar hisseye özgü sapmaları düzeltir.
    """
    ortak = _lgbm_egit(egitim, hedef)
    tahmin = ortak.predict_proba(test[OZELLIKLER])[:, 1]
    kod_egitim = egitim.index.get_level_values("kod")
    kod_test = test.index.get_level_values("kod")
    for kod in kod_test.unique():
        e = egitim[kod_egitim == kod]
        if len(e) < 750:   # ~3 yıldan az geçmiş: ince ayar yapma
            continue
        model = lgb.LGBMClassifier(**{**LGBM_AYARLARI, "n_estimators": ek_agac,
                                      "learning_rate": 0.01, "min_child_samples": 100})
        model.fit(e[OZELLIKLER], e[hedef], init_model=ortak.booster_)
        t = np.asarray(kod_test == kod)
        tahmin[t] = model.predict_proba(test.loc[t, OZELLIKLER])[:, 1]
    return tahmin


MODELLER = {
    "hep_yukselir": _hep_yukselir,
    "rastgele": _rastgele,
    "lojistik": _sklearn(LogisticRegression(C=0.1, max_iter=2000)),
    "rastgele_orman": _sklearn(RandomForestClassifier(
        n_estimators=200, max_depth=6, min_samples_leaf=500, max_features=0.5,
        n_jobs=-1, random_state=TOHUM)),
    "lightgbm": _lightgbm,
    "lightgbm_grup": _lightgbm_grup,
    "lightgbm_ince_ayar": _lightgbm_ince_ayar,
}


# ---------------------------------------------------------------------------
# Walk-forward döngüsü
# ---------------------------------------------------------------------------

def egitim_test_ayir(tablo: pd.DataFrame, yil: int, hedef: str = "hedef_yon",
                     bitis_sutunu: str = "hedef_bitis_yon") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Bir test yılı için eğitim ve test kümelerini ayırır.

    Eğitim: hedefi test yılı başlamadan BİTMİŞ satırlar (purging).
    Test: o yılın satırları (hedefi bilinenler).
    """
    baslangic = pd.Timestamp(f"{yil}-01-01")
    bitis = pd.Timestamp(f"{yil}-12-31")
    tarih = tablo.index.get_level_values("tarih")
    bilinen = tablo[hedef].notna() & tablo["getiri_60"].notna()
    egitim = tablo[bilinen & (tablo[bitis_sutunu] < baslangic)]
    test = tablo[bilinen & (tarih >= baslangic) & (tarih <= bitis)]
    return egitim, test


# ---------------------------------------------------------------------------
# Volatilite (regresyon) deneyi
# ---------------------------------------------------------------------------

def _vol_gecmis(egitim, test, hedef):
    """Baseline: gelecek 20 günün volatilitesi = geçmiş 20 günün volatilitesi."""
    return test["volatilite_20"].values


def _vol_lightgbm(egitim, test, hedef):
    """LightGBM regresyon; log ölçekte eğitilir (volatilite sağa çarpık dağılır)."""
    model = lgb.LGBMRegressor(**LGBM_AYARLARI)
    model.fit(egitim[OZELLIKLER], np.log(egitim[hedef]))
    return np.exp(model.predict(test[OZELLIKLER]))


VOL_MODELLERI = {"vol_gecmis": _vol_gecmis, "vol_lightgbm": _vol_lightgbm}


def walk_forward_vol(tablo: pd.DataFrame, test_yillari: list[int] = TEST_YILLARI) -> pd.DataFrame:
    """20 günlük gelecek volatilitesi için walk-forward (hedefi 20 gün ileri bakar)."""
    sonuclar = []
    for yil in test_yillari:
        egitim, test = egitim_test_ayir(tablo, yil, "hedef_vol_20", "hedef_bitis_vol")
        egitim = egitim[egitim["volatilite_20"].notna() & (egitim["hedef_vol_20"] > 0)]
        test = test[test["volatilite_20"].notna() & (test["hedef_vol_20"] > 0)]
        for ad, fn in VOL_MODELLERI.items():
            sonuclar.append(pd.DataFrame({"model": ad, "yil": yil, "tahmin": fn(egitim, test, "hedef_vol_20"),
                                          "gercek": test["hedef_vol_20"].values}, index=test.index))
    return pd.concat(sonuclar)


def walk_forward(tablo: pd.DataFrame, modeller: list[str], test_yillari: list[int] = TEST_YILLARI,
                 hedef: str = "hedef_yon", bitis_sutunu: str = "hedef_bitis_yon") -> pd.DataFrame:
    """Her test yılı için modelleri yeniden eğitir; tüm tahminleri tek tabloda döner."""
    sonuclar = []
    for yil in test_yillari:
        egitim, test = egitim_test_ayir(tablo, yil, hedef, bitis_sutunu)
        if test.empty:
            continue
        log.info("%d: eğitim %d satır, test %d satır", yil, len(egitim), len(test))
        for ad in modeller:
            olasilik = MODELLER[ad](egitim, test, hedef)
            sonuclar.append(pd.DataFrame({
                "model": ad, "yil": yil, "olasilik": olasilik,
                "gercek": test[hedef].values, "getiri": test["hedef_getiri"].values,
            }, index=test.index))
    return pd.concat(sonuclar)
