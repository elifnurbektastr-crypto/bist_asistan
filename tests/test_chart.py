"""Grafik aracının Python tarafı ve JavaScript testlerinin çalıştırılması."""

import json
import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src import config
from src.charting import chart
from tests.test_indicators import sahte_hisse


def ham_hisse():
    """2:1 bölünmeli küçük ham fiyat tablosu (3. gün bölünme)."""
    idx = pd.bdate_range("2024-01-01", periods=5)
    k = np.array([100.0, 102.0, 51.0, 52.0, 53.0])
    return pd.DataFrame({"acilis": k, "yuksek": k * 1.01, "dusuk": k * 0.99, "kapanis": k,
                         "hacim": [10.0, 10, 20, 20, 20], "bolunme": [0, 0, 2.0, 0, 0]}, index=idx)


def test_bolunme_duzeltilmis_son_fiyat_aynı_ucurum_yok():
    d = chart.bolunme_duzeltilmis(ham_hisse())
    assert d["kapanis"].tolist() == pytest.approx([50, 51, 51, 52, 53])
    assert d["hacim"].tolist() == pytest.approx([20, 20, 20, 20, 20])


def test_haftalik_mum():
    idx = pd.bdate_range("2024-01-01", periods=10)   # iki tam hafta
    ohlc = pd.DataFrame({"acilis": np.arange(10.0), "yuksek": np.arange(10.0) + 5, "dusuk": np.arange(10.0) - 5,
                         "kapanis": np.arange(10.0) + 1, "hacim": 1.0}, index=idx)
    h = chart.yeniden_ornekle(ohlc, "Haftalık")
    assert len(h) == 2
    ilk = h.iloc[0]
    assert (ilk["acilis"], ilk["yuksek"], ilk["dusuk"], ilk["kapanis"], ilk["hacim"]) == (0, 9, -5, 5, 5)
    assert h.index[0] == pd.Timestamp("2024-01-05")   # haftanın son işlem günü


def test_macd_ve_bollinger():
    k = pd.Series(np.full(60, 100.0))
    m = chart.macd(k)
    assert m.abs().max().max() == pytest.approx(0)      # sabit fiyatta MACD sıfır
    b = chart.bollinger(pd.Series(np.arange(40.0))).dropna()   # ilk 19 gün pencere dolmadığı için boş
    assert len(b) == 21 and (b["ust"] > b["orta"]).all() and (b["alt"] < b["orta"]).all()


def test_periyotlari_oku():
    assert chart.periyotlari_oku("20, 50 200, 50, abc, 1, 999") == [20, 50, 200]


def test_sekil_json_ve_paneller():
    df = sahte_hisse(n=400)
    df["bolunme"] = 0.0
    sekil = chart.sekil_olustur(df, "TEST", ma=[20, 50], rsi_acik=True, macd_acik=True, bollinger_acik=True)
    json.dumps(sekil)                                   # bileşene gönderilebilmeli
    eksenler = [k for k in sekil["layout"] if k.startswith("yaxis")]
    assert len(eksenler) == 4                           # fiyat, hacim, RSI, MACD
    adlar = [t.get("name") for t in sekil["data"]]
    assert "MA 20" in adlar and "MA 50" in adlar and "Bollinger (20, 2)" in adlar


def test_indikator_donem_basinda_dolu():
    """MA uzun geçmişle hesaplandığı için kesilen dönemin ilk gününde de değer olmalı."""
    df = sahte_hisse(n=600)
    df["bolunme"] = 0.0
    sekil = chart.sekil_olustur(df, "TEST", donem_gun=126, ma=[200])
    ma = next(t for t in sekil["data"] if t.get("name") == "MA 200")
    y = ma["y"]
    if isinstance(y, dict):   # plotly ikili dizi kodlaması
        import base64
        y = np.frombuffer(base64.b64decode(y["bdata"]), dtype=y["dtype"])
    assert not np.isnan(np.asarray(y, dtype=float)[0])


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js yok")
def test_javascript_testleri():
    sonuc = subprocess.run(["node", "--test", "tests/js/grafik.test.mjs"], cwd=config.KOK_DIZIN,
                           capture_output=True, text=True, encoding="utf-8")
    assert sonuc.returncode == 0, sonuc.stdout + sonuc.stderr
