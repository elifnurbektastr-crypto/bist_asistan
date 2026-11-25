"""Temettü modülünün testleri."""

import pandas as pd
import pytest

from src.data.dividends import (filtrele, kesintisiz_yil, temettu_gecmisi, temettu_ozeti,
                                yaklasan_durumu)
from src.data.fetch import standartlastir

BUGUN = pd.Timestamp("2024-06-01")


def test_temettu_gecmisi_verim_ham_fiyatla(yf_ornek):
    gecmis = temettu_gecmisi(standartlastir(yf_ornek))
    assert gecmis["tl"].tolist() == pytest.approx([2.0, 1.0])
    assert gecmis["verim"].tolist() == pytest.approx([2 / 100, 1 / 53])


def test_ozet_verimi_bugunku_hisse_bazinda(yf_ornek):
    ozet = temettu_ozeti({"ORNEK.IS": standartlastir(yf_ornek)}, BUGUN)
    satir = ozet.loc["ORNEK"]
    # 2 TL bölünmeden önce ödendi = bugünkü bazda 1 TL; toplam 1 + 1 = 2 TL
    assert satir["son12ay_tl"] == pytest.approx(2.0)
    assert satir["son12ay_verim"] == pytest.approx(2.0 / 56)
    assert satir["son_temettu_tl"] == pytest.approx(1.0)
    assert satir["son12ay_odeme_sayisi"] == 2


@pytest.mark.parametrize("yillar, beklenen", [
    ([2024, 2023, 2022], 3),
    ([2023, 2022, 2020], 2),   # bu yıl henüz yok: geçen yıldan say, 2021 boşluk
    ([2024, 2022], 1),
    ([2020], 0),
])
def test_kesintisiz_yil(yillar, beklenen):
    tarihler = pd.DatetimeIndex([f"{y}-05-01" for y in yillar])
    assert kesintisiz_yil(tarihler, BUGUN) == beklenen


def test_yaklasan_durumu():
    assert yaklasan_durumu(pd.Timestamp("2024-06-11"), BUGUN) == ("yaklaşan", 10)
    assert yaklasan_durumu(pd.Timestamp("2024-05-01"), BUGUN)[0].startswith("tarih geçmiş")
    assert yaklasan_durumu(None, BUGUN) == ("bilgi yok", None)


def test_filtrele():
    tablo = pd.DataFrame({
        "son12ay_verim": [0.08, 0.02, 0.06],
        "son12ay_tl": [5.0, 1.0, 3.0],
        "kesintisiz_yil": [5, 1, 3],
        "durum": ["yaklaşan", "yaklaşan", "tarih geçmiş (güncel bilgi yok)"],
        "kalan_gun": [10, 40, -5],
        "sektor": ["Banka", "Sanayi", "Banka"],
    }, index=["A", "B", "C"])
    assert filtrele(tablo, min_verim=0.05).index.tolist() == ["A", "C"]
    assert filtrele(tablo, min_tl=2, min_kesintisiz_yil=4).index.tolist() == ["A"]
    assert filtrele(tablo, gun_icinde=30).index.tolist() == ["A"]
    assert filtrele(tablo, sektor=["Banka"]).index.tolist() == ["A", "C"]
    assert len(filtrele(tablo)) == 3
