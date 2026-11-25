"""Özellik ve hedef hesaplarının testleri — özellikle geleceğe bakma (look-ahead) kontrolü."""

import numpy as np
import pandas as pd
import pytest

from src.features.indicators import (TUM_OZELLIKLER, hedefler, hisse_ozellikleri, makro_ozellikleri,
                                     rsi, veri_seti_olustur)


def sahte_hisse(n: int = 150, tohum: int = 0) -> pd.DataFrame:
    """Rastgele yürüyüşle üretilmiş standart fiyat tablosu."""
    rng = np.random.default_rng(tohum)
    tarih = pd.bdate_range("2020-01-01", periods=n)
    kapanis = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    acilis = kapanis * (1 + rng.normal(0, 0.005, n))
    df = pd.DataFrame({
        "acilis": acilis, "yuksek": np.maximum(acilis, kapanis) * 1.01,
        "dusuk": np.minimum(acilis, kapanis) * 0.99, "kapanis": kapanis,
        "hacim": rng.integers(1_000, 10_000, n).astype(float),
    }, index=tarih)
    for s in ["acilis", "yuksek", "dusuk", "kapanis"]:
        df[f"duz_{s}"] = df[s]
    return df


def test_ozellikler_gelecege_bakmaz():
    """t gününden sonraki veri değişse de t günündeki özellikler değişmemeli."""
    df = sahte_hisse()
    t = df.index[100]
    tam = hisse_ozellikleri(df).loc[:t]
    kesik = hisse_ozellikleri(df.loc[:t])
    pd.testing.assert_frame_equal(tam, kesik)

    bozuk = df.copy()
    bozuk.loc[bozuk.index > t, ["duz_kapanis", "hacim"]] *= 5
    pd.testing.assert_frame_equal(hisse_ozellikleri(bozuk).loc[:t], tam)


def test_yon_hedefi_ertesi_gun_acilistan_alinir():
    df = sahte_hisse()
    h = hedefler(df)
    i = 50
    beklenen = df["duz_acilis"].iloc[i + 6] / df["duz_acilis"].iloc[i + 1] - 1
    assert h["hedef_getiri"].iloc[i] == pytest.approx(beklenen)
    assert h["hedef_yon"].iloc[i] == float(beklenen > 0)
    assert h["hedef_bitis_yon"].iloc[i] == df.index[i + 6]
    assert h["hedef_yon"].iloc[-6:].isna().all()   # geleceği bilinmeyen son günler boş


def test_volatilite_hedefi_sonraki_20_gun():
    df = sahte_hisse()
    h = hedefler(df)
    g = df["duz_kapanis"].pct_change()
    i = 40
    beklenen = g.iloc[i + 1:i + 21].std() * np.sqrt(252)
    assert h["hedef_vol_20"].iloc[i] == pytest.approx(beklenen)


def test_rsi_sinirlar():
    yukselen = pd.Series(np.arange(1, 40, dtype=float))
    assert rsi(yukselen).iloc[-1] == pytest.approx(100)
    rastgele = sahte_hisse()["duz_kapanis"]
    r = rsi(rastgele).dropna()
    assert ((r >= 0) & (r <= 100)).all()


def test_tufe_yayin_tarihinden_once_kullanilmaz():
    """Ekim TÜFE'si 3 Kasım'da açıklanır: 2 Kasım'da hâlâ Eylül verisi görülmeli."""
    aylar = pd.date_range("2023-01-01", "2024-10-01", freq="MS")
    tufe = pd.Series(np.linspace(100, 200, len(aylar)), index=aylar)
    makro = pd.DataFrame({"tufe": tufe, "tufe_yayin_tarihi": aylar + pd.DateOffset(months=1, days=2),
                          "politika_faizi": 50.0})
    takvim = pd.bdate_range("2024-10-28", "2024-11-08")
    oz = makro_ozellikleri(makro, takvim)
    eylul = tufe["2024-09-01"] / tufe["2023-09-01"] - 1
    ekim = tufe["2024-10-01"] / tufe["2023-10-01"] - 1
    assert oz.loc["2024-11-01", "yillik_enflasyon"] == pytest.approx(eylul)
    assert oz.loc["2024-11-04", "yillik_enflasyon"] == pytest.approx(ekim)   # 3 Kasım pazar
    assert oz["politika_faizi"].iloc[-1] == pytest.approx(0.5)


def test_veri_seti_bicimi():
    veri = {"AAA.IS": sahte_hisse(tohum=1), "BBB.IS": sahte_hisse(tohum=2)}
    endeks = sahte_hisse(tohum=3)
    tablo = veri_seti_olustur(veri, endeks)
    assert tablo.index.names == ["tarih", "kod"]
    assert set(tablo.index.get_level_values("kod")) == {"AAA", "BBB"}
    assert set(TUM_OZELLIKLER).issubset(tablo.columns)
    satir = tablo.xs("AAA", level="kod").iloc[80]
    assert satir["goreli_getiri_20"] == pytest.approx(satir["getiri_20"] - satir["endeks_getiri_20"])
