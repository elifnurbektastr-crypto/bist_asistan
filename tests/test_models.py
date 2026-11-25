"""Walk-forward eğitim ve değerlendirme testleri (küçük sahte veriyle)."""

import numpy as np
import pandas as pd
import pytest

from src.features.indicators import veri_seti_olustur
from src.models import evaluate, train
from tests.test_indicators import sahte_hisse


@pytest.fixture(scope="module")
def tablo():
    veri = {f"H{i}.IS": sahte_hisse(n=1300, tohum=i) for i in range(6)}
    return veri_seti_olustur(veri, sahte_hisse(n=1300, tohum=99))


def test_purging_egitim_hedefi_teste_tasmaz(tablo):
    yil = 2023
    egitim, test = train.egitim_test_ayir(tablo, yil)
    baslangic = pd.Timestamp(f"{yil}-01-01")
    assert (egitim["hedef_bitis_yon"] < baslangic).all()
    assert (egitim.index.get_level_values("tarih") < baslangic).all()
    assert (test.index.get_level_values("tarih").year == yil).all()
    # Purging, test başlangıcından hemen önceki birkaç günü eğitimden çıkarmış olmalı
    son_egitim = egitim.index.get_level_values("tarih").max()
    assert (baslangic - son_egitim).days >= 6


@pytest.mark.parametrize("model", list(train.MODELLER))
def test_tum_modeller_calisir_ve_olasilik_uretir(tablo, model):
    tahmin = train.walk_forward(tablo, [model], test_yillari=[2024])
    assert len(tahmin) > 0
    assert tahmin["olasilik"].between(0, 1).all()
    assert (tahmin["model"] == model).all()


def test_rastgele_veride_model_sansi_gecmez(tablo):
    """Rastgele yürüyüşte öğrenilecek bir şey yok: doğruluk %50 civarında kalmalı."""
    tahmin = train.walk_forward(tablo, ["lightgbm"], test_yillari=[2023, 2024])
    ozet = evaluate.ozet_tablo(tahmin)
    assert 0.42 < ozet.loc["lightgbm", "dogruluk"] < 0.58
    assert evaluate.asiri_ogrenme_alarmi(ozet) == []


def test_metrikler_bilinen_ornek():
    idx = pd.MultiIndex.from_product([pd.bdate_range("2024-01-01", periods=2), list("ABCDEFGHIJ")],
                                     names=["tarih", "kod"])
    olasilik = np.tile(np.linspace(0.1, 0.9, 10), 2)
    getiri = np.tile(np.linspace(-0.05, 0.05, 10), 2)   # olasılık arttıkça getiri artıyor
    tahmin = pd.DataFrame({"olasilik": olasilik, "gercek": (getiri > 0).astype(float), "getiri": getiri}, index=idx)
    m = evaluate.metrikler(tahmin)
    assert m["dogruluk"] == pytest.approx(1.0)
    assert m["auc"] == pytest.approx(1.0)
    assert m["ust_alt_dilim_farki"] > 0
    assert m["al_sinyali_orani"] == pytest.approx(0.5)


def test_asiri_ogrenme_alarmi():
    ozet = pd.DataFrame({"dogruluk": [0.53, 0.71]}, index=["iyi", "supheli"])
    assert evaluate.asiri_ogrenme_alarmi(ozet) == ["supheli"]


def test_esik_analizi_kapsama_azalir():
    rng = np.random.default_rng(0)
    tahmin = pd.DataFrame({"olasilik": rng.random(1000), "gercek": rng.integers(0, 2, 1000),
                           "getiri": rng.normal(0, 0.03, 1000)})
    e = evaluate.esik_analizi(tahmin)
    assert e["kapsama"].is_monotonic_decreasing


def test_volatilite_walk_forward(tablo):
    tahmin = train.walk_forward_vol(tablo, test_yillari=[2024])
    assert set(tahmin["model"]) == {"vol_gecmis", "vol_lightgbm"}
    assert (tahmin["tahmin"] > 0).all()
    m = evaluate.vol_metrikleri(tahmin[tahmin.model == "vol_gecmis"])
    assert m["ort_mutlak_hata"] >= 0


def test_guncel_tahmin_son_gunu_kullanir(tablo):
    from src.models import predict
    sonuc = predict.guncel_tahminler(tablo, model="lightgbm")
    assert sonuc.attrs["tarih"] == tablo.index.get_level_values("tarih").max().date()
    assert sonuc["yukselis_olasiligi"].between(0, 1).all()
    assert set(sonuc["sinyal"]) <= {"güçlü al", "zayıf al", "al değil"}
    assert (sonuc["beklenen_vol_20"] > 0).all()
