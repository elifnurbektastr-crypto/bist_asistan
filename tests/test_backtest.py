"""Backtest motoru, stratejiler ve metriklerin testleri (elle hesaplanabilir küçük örneklerle)."""

import numpy as np
import pandas as pd
import pytest

from src.backtest import engine, metrics, strategies
from tests.test_indicators import sahte_hisse


def fiyat(acilislar, baslangic="2024-01-01"):
    idx = pd.bdate_range(baslangic, periods=len(acilislar))
    a = np.array(acilislar, dtype=float)
    return pd.DataFrame({"duz_acilis": a, "duz_kapanis": a}, index=idx)


# --- Motor ---------------------------------------------------------------

def test_al_ve_tut_acilistan_acilisa_ve_tek_maliyet():
    df = fiyat([100, 110, 121, 133.1])
    t = engine.backtest(df, strategies.al_ve_tut(df), maliyet=0.001)
    # 1. gün kararı 2. gün açılışında uygulanır: 110 -> 133.1 (son günün getirisi bilinmez)
    assert t["pozisyon"].tolist() == [0.0, 1.0, 1.0]
    assert t["sermaye"].iloc[-1] == pytest.approx((1 - 0.001) * 1.1 * 1.1 - 0.0, rel=1e-3)
    assert t["maliyet"].sum() == pytest.approx(0.001)


def test_sinyal_ertesi_gun_uygulanir():
    df = fiyat([100, 100, 100, 200, 200])
    hedef = pd.Series([0, 0, 1, 1, 1], index=df.index, dtype=float)   # 3. gün kapanışında 'al'
    t = engine.backtest(df, hedef, maliyet=0.0)
    # 3. gün kapanışındaki karar 4. gün açılışında (200) uygulanır: 3->4 sıçramasını yakalayamaz
    assert t["sermaye"].iloc[-1] == pytest.approx(1.0)


def test_maliyet_sadece_degisimde():
    df = fiyat([100] * 6)
    hedef = pd.Series([1, 1, 0, 0, 1, 1], index=df.index, dtype=float)
    t = engine.backtest(df, hedef, maliyet=0.01)
    assert t["maliyet"].tolist() == pytest.approx([0, 0.01, 0, 0.01, 0])   # al, sat, al


def test_nakit_faiz_kazanir():
    df = fiyat([100] * 4)
    faiz = pd.Series(0.252, index=df.index)   # yıllık %25,2 -> günlük %0,1
    t = engine.backtest(df, pd.Series(0.0, index=df.index), maliyet=0.0, nakit_faizi=faiz)
    assert t["strateji_getirisi"].tolist() == pytest.approx([0.001] * 3)


def test_gelecek_fiyat_gecmis_sonucu_degistirmez():
    df = sahte_hisse(n=200)
    t1 = engine.backtest(df, strategies.ma_kesisim(df))
    bozuk = df.copy()
    bozuk.loc[bozuk.index[150:], ["duz_acilis", "duz_kapanis"]] *= 3
    t2 = engine.backtest(bozuk, strategies.ma_kesisim(bozuk))
    # 148. güne kadarki sermaye aynı kalmalı (149. günün getirisi 150. açılışa bağlı)
    pd.testing.assert_series_equal(t1["sermaye"].iloc[:148], t2["sermaye"].iloc[:148])


# --- Stratejiler ------------------------------------------------------------

@pytest.mark.parametrize("ad", list(strategies.STRATEJILER))
def test_stratejiler_gelecege_bakmaz(ad):
    df = sahte_hisse(n=200)
    fn = strategies.STRATEJILER[ad]
    t = df.index[120]
    pd.testing.assert_series_equal(fn(df).loc[:t], fn(df.loc[:t]))


def test_rsi_stratejisi_esiklerde_durum_degistirir():
    df = fiyat(list(range(100, 60, -2)) + list(range(60, 140, 4)))   # sert düşüş, sonra sert yükseliş
    poz = strategies.rsi_stratejisi(df)
    assert poz.iloc[25] == 1.0        # düşüş sonrası aşırı satım: pozisyonda
    assert poz.iloc[-1] == 0.0        # yükseliş sonrası aşırı alım: çıkmış


def test_ml_sinyali_5_gunde_bir_karar_ve_tutma():
    df = fiyat([100] * 12)
    olasilik = pd.Series([0.7, 0.2, 0.2, 0.2, 0.2, 0.3, 0.9, 0.9, 0.9, 0.9, 0.65, 0.1], index=df.index)
    poz = strategies.ml_sinyali(df, olasilik, esik=0.6, ufuk=5)
    assert poz.tolist() == [1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1]


# --- Portföy -------------------------------------------------------------------

def test_portfoy_agirliklari_nakit_ve_ters_vol():
    olasilik = pd.Series({"A": 0.7, "B": 0.65, "C": 0.55, "D": 0.62})
    w = engine.portfoy_agirliklari(olasilik, esik=0.6, n=4)
    assert set(w.index) == {"A", "B", "D"} and w.sum() == pytest.approx(0.75)   # 1/4 nakitte
    vol = pd.Series({"A": 0.2, "B": 0.4, "D": 0.4})
    wv = engine.portfoy_agirliklari(olasilik, esik=0.6, n=4, vol=vol)
    assert wv.sum() == pytest.approx(0.75) and wv["A"] == pytest.approx(2 * wv["B"])


def test_portfoy_karar_ertesi_gun_uygulanir_ve_devir_maliyeti():
    idx = pd.bdate_range("2024-01-01", periods=10)
    getiriler = pd.DataFrame({"A": 0.01, "B": -0.01}, index=idx)
    olasilik = pd.DataFrame({"A": 0.9, "B": 0.1}, index=idx)
    t = engine.portfoy_backtest(getiriler, olasilik, esik=0.6, n=1, ufuk=5, maliyet=0.001)
    assert t.index[0] == idx[1]                      # 1. gün kararı 2. gün uygulanır
    assert (t["hisse_sayisi"] == 1).all()
    assert t["hisse_getirisi"].tolist() == pytest.approx([0.01] * len(t))
    assert t["maliyet"].iloc[0] == pytest.approx(0.001) and t["maliyet"].iloc[1:].sum() == 0


# --- Metrikler -------------------------------------------------------------------

def test_maksimum_dusus_ve_cagr():
    egri = pd.Series([1.0, 1.2, 0.9, 1.5, 1.2])
    assert metrics.maksimum_dusus(egri) == pytest.approx(0.9 / 1.2 - 1)
    getiri = pd.Series([0.001] * 252)
    assert metrics.cagr(getiri) == pytest.approx(1.001 ** 252 - 1)


def test_sharpe_risksiz_faizi_duser():
    rng = np.random.default_rng(0)
    getiri = pd.Series(rng.normal(0.4 / 252, 0.001, 2000))   # yıllık %40 getiri, düşük gürültü
    assert metrics.sharpe(getiri, 0.0) > metrics.sharpe(getiri, 0.36) > 0


def test_islem_istatistikleri():
    poz = pd.Series([0, 1, 1, 0, 1, 0], dtype=float)
    getiri = pd.Series([0.0, 0.05, -0.01, 0.0, -0.02, 0.0])
    sayi, kazanma = metrics.islem_istatistikleri(poz, getiri)
    assert sayi == 2 and kazanma == pytest.approx(0.5)
