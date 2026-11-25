"""Kalite kontrolleri, önbellek ve ayar fonksiyonlarının testleri."""

import pandas as pd
import pytest

from src import config
from src.data import cache
from src.data.fetch import standartlastir
from src.data.quality import bolunme_kontrolu, kalite_raporu


def test_bolunme_varsayimi_dogruysa_sapma_bir(yf_ornek):
    kontrol = bolunme_kontrolu(standartlastir(yf_ornek))
    assert len(kontrol) == 1
    assert kontrol["sapma"].iloc[0] == pytest.approx(1.0)


def test_bolunme_varsayimi_yanlissa_sapma_oran_kadar(yf_ornek):
    # yfinance Close aslında ham olsaydı: bölünme öncesi fiyatlar /2 edilmemiş olurdu
    # (Adj Close ise her durumda pürüzsüzdür, ona dokunmuyoruz)
    ham_close = yf_ornek.copy()
    ham_close.loc[ham_close.index[:3], ["Open", "High", "Low", "Close"]] *= 2
    kontrol = bolunme_kontrolu(standartlastir(ham_close))
    assert kontrol["sapma"].iloc[0] == pytest.approx(2.0)


def test_kalite_raporu_limit_asimi_ve_eksik_gun(yf_ornek):
    df = standartlastir(yf_ornek)
    df.loc["2024-01-10", ["duz_kapanis"]] *= 1.3   # %30 sahte sıçrama
    takvim = pd.bdate_range("2024-01-02", "2024-01-11")  # 12.01 dahil değil, 8 gün
    takvim = takvim.append(pd.DatetimeIndex(["2024-01-12"]))
    rapor = kalite_raporu(df.drop(pd.Timestamp("2024-01-08")), takvim)
    assert rapor["limit_asimi"] == 2               # sıçrama + geri dönüş
    assert rapor["eksik_gun"] == 1                 # 08.01 silindi
    assert rapor["bolunme"] == 1 and rapor["temettu"] == 2
    assert rapor["ohlc_tutarsiz"] == 0


def test_onbellek_yaz_oku(tmp_path, yf_ornek):
    df = standartlastir(yf_ornek)
    cache.yaz(df, "TRY=X", dizin=tmp_path)
    assert (tmp_path / "fiyat" / "TRY_X.parquet").exists()
    pd.testing.assert_frame_equal(cache.oku("TRY=X", dizin=tmp_path), df, check_freq=False)
    assert cache.oku("YOK.IS", dizin=tmp_path) is None


def test_yf_sembol():
    assert config.yf_sembol(" thyao ") == "THYAO.IS"
    assert config.yf_sembol("XU100.IS") == "XU100.IS"
    assert config.yf_sembol("TRY=X") == "TRY=X"


def test_hisse_evreni_csv_ve_yedek_liste(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "REFERANS_DIZINI", tmp_path)
    assert config.hisse_evreni("bist100") == config.CEKIRDEK_HISSELER
    pd.DataFrame({"kod": ["garan", "THYAO", "GARAN"]}).to_csv(tmp_path / "bist100.csv", index=False)
    assert config.hisse_evreni("bist100") == ["GARAN", "THYAO"]


def test_supheli_sicrama_ve_elle_duzeltme(yf_ornek):
    from src.data.fetch import elle_duzeltmeleri_uygula
    from src.data.quality import supheli_sicramalar
    # Yahoo 05.01 bölünmesini kaydetmemiş olsun: düzeltilmiş seri de ham gibi -%50 düşer
    kacirilmis = yf_ornek.copy()
    once = kacirilmis.index[:3]
    kacirilmis.loc[once, ["Open", "High", "Low", "Close", "Adj Close", "Dividends"]] *= 2
    kacirilmis["Stock Splits"] = 0.0
    df = standartlastir(kacirilmis)
    supheli = supheli_sicramalar(df)
    assert supheli.index.tolist() == [pd.Timestamp("2024-01-05")]
    assert supheli["tahmini_oran"].iloc[0] == pytest.approx(2.0)

    duzeltme = pd.DataFrame({"tarih": ["2024-01-05"], "oran": [2.0]})
    duzeltilmis = elle_duzeltmeleri_uygula(df, duzeltme)
    dogru = standartlastir(yf_ornek)
    pd.testing.assert_series_equal(duzeltilmis["duz_kapanis"], dogru["duz_kapanis"])
    pd.testing.assert_series_equal(duzeltilmis["kapanis"], dogru["kapanis"])
    assert duzeltilmis.loc["2024-01-03", "temettu_duz"] == pytest.approx(1.0)
    assert len(supheli_sicramalar(duzeltilmis)) == 0
    # Yahoo bölünmeyi zaten kaydetmişse elle düzeltme ikinci kez uygulanmaz
    pd.testing.assert_frame_equal(elle_duzeltmeleri_uygula(dogru, duzeltme), dogru)


def test_elle_duzeltme_yahoonun_yanlis_oranini_degistirir(yf_ornek):
    from src.data.fetch import elle_duzeltmeleri_uygula
    # Yahoo 05.01 bölünmesini 2 yerine 4 olarak kaydetmiş olsun
    yanlis = yf_ornek.copy()
    once = yanlis.index[:3]
    yanlis.loc[once, ["Open", "High", "Low", "Close", "Adj Close", "Dividends"]] /= 2
    yanlis.loc["2024-01-05", "Stock Splits"] = 4.0
    df = standartlastir(yanlis)
    dogru = standartlastir(yf_ornek)
    pd.testing.assert_series_equal(df["kapanis"], dogru["kapanis"])   # ham fiyat zaten doğru
    duzeltilmis = elle_duzeltmeleri_uygula(df, pd.DataFrame({"tarih": ["2024-01-05"], "oran": [2.0]}))
    pd.testing.assert_series_equal(duzeltilmis["duz_kapanis"], dogru["duz_kapanis"])
    assert duzeltilmis.loc["2024-01-05", "bolunme"] == 2.0
