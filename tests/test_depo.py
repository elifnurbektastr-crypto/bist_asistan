"""Duyuru ve geri bildirim deposu testleri."""

import pytest

from src.depo import NOT_SINIRI, SQLiteDepo


@pytest.fixture
def depo(tmp_path):
    return SQLiteDepo(tmp_path / "test.db")


def test_duyuru_ekle_kapat_ve_sure(depo):
    a = depo.duyuru_ekle("Bakım", "Yarın veri güncellenmeyecek", "uyari", bitis="2026-12-01")
    b = depo.duyuru_ekle("Yeni özellik", "Temettü sekmesi eklendi")
    assert depo.aktif_duyurular("2026-11-30")["id"].tolist() == [b, a]
    assert depo.aktif_duyurular("2026-12-02")["id"].tolist() == [b]   # süresi doldu
    depo.duyuru_kapat(b)
    assert depo.aktif_duyurular("2026-11-30")["id"].tolist() == [a]
    assert len(depo.tum_duyurular()) == 2


def test_duyuru_gecersiz(depo):
    with pytest.raises(ValueError):
        depo.duyuru_ekle("", "metin")
    with pytest.raises(ValueError):
        depo.duyuru_ekle("başlık", "metin", tur="reklam")


def test_geri_bildirim_kisa_not(depo):
    depo.geri_bildirim_ekle("Temettü", 1, "x" * 500)
    depo.geri_bildirim_ekle("Backtest", -1)
    gb = depo.geri_bildirimler()
    assert len(gb) == 2
    assert len(gb.loc[gb["sekme"] == "Temettü", "notu"].iloc[0]) == NOT_SINIRI
    assert gb.loc[gb["sekme"] == "Backtest", "notu"].isna().all()
    with pytest.raises(ValueError):
        depo.geri_bildirim_ekle("Temettü", 5)


def test_sql_enjeksiyonu_zararsiz(depo):
    depo.geri_bildirim_ekle("Analiz'); DROP TABLE geri_bildirimler;--", 1, "'; DELETE FROM duyurular;--")
    assert len(depo.geri_bildirimler()) == 1
