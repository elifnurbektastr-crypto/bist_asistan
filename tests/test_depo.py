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


# --- Supabase deposu: ağ yok, zincirleme sorgu arayüzünü taklit eden sahte istemci ---------------

class _Cevap:
    def __init__(self, data):
        self.data = data


class _Sorgu:
    def __init__(self, tablo, islem, veri=None):
        self.tablo, self.islem, self.veri, self.filtre, self.ters = tablo, islem, veri, {}, False

    def eq(self, sutun, deger):
        self.filtre[sutun] = deger
        return self

    def order(self, sutun, desc=False):
        self.ters = desc
        return self

    def execute(self):
        satirlar = self.tablo.satirlar
        if self.islem == "insert":
            satir = {"id": len(satirlar) + 1, "aktif": True, "olusturma": "2026-11-25T10:00:00",
                     "zaman": "2026-11-25T10:00:00", "bitis": None, **self.veri}
            satirlar.append(satir)
            return _Cevap([satir] if self.tablo.geri_dondur else [])
        if self.islem == "update":
            for s in satirlar:
                if all(s.get(k) == v for k, v in self.filtre.items()):
                    s.update(self.veri)
            return _Cevap([])
        secili = [s for s in satirlar if all(s.get(k) == v for k, v in self.filtre.items())]
        return _Cevap(sorted(secili, key=lambda s: s["id"], reverse=self.ters))


class _Tablo:
    def __init__(self):
        self.satirlar, self.geri_dondur = [], True

    def select(self, *_):
        return _Sorgu(self, "select")

    def insert(self, veri, returning=None):
        self.geri_dondur = getattr(returning, "value", "representation") != "minimal"
        return _Sorgu(self, "insert", veri)

    def update(self, veri):
        return _Sorgu(self, "update", veri)


class _SahteSupabase:
    def __init__(self):
        self.tablolar = {"duyurular": _Tablo(), "geri_bildirimler": _Tablo()}

    def table(self, ad):
        return self.tablolar[ad]


def test_supabase_deposu_ayni_arayuz():
    from src.depo import SupabaseDepo
    sahte = _SahteSupabase()
    depo = SupabaseDepo(istemci=sahte)
    a = depo.duyuru_ekle("Bakım", "Yarın veri yok", "uyari", bitis="2026-12-01")
    b = depo.duyuru_ekle("Yeni", "Temettü sekmesi")
    assert depo.aktif_duyurular("2026-12-02")["id"].tolist() == [b]
    depo.duyuru_kapat(b)
    assert depo.aktif_duyurular("2026-11-30")["id"].tolist() == [a]
    depo.geri_bildirim_ekle("Grafik", 1, "x" * 300)
    assert sahte.tablolar["geri_bildirimler"].geri_dondur is False   # eklenen satır geri istenmez
    gb = depo.geri_bildirimler()
    assert list(gb.columns) == ["id", "zaman", "sekme", "puan", "notu"]
    assert len(gb.loc[0, "notu"]) == NOT_SINIRI
    with pytest.raises(ValueError):
        depo.geri_bildirim_ekle("Grafik", 3)


def test_depo_secimi(monkeypatch):
    from src import bulut
    from src import depo as depo_modulu
    monkeypatch.setattr(bulut, "ayarlar", lambda: {"url": "", "publishable": "", "secret": ""})
    assert isinstance(depo_modulu.depo_al(), depo_modulu.SQLiteDepo)
    monkeypatch.setattr(bulut, "ayarlar",
                        lambda: {"url": "https://x.supabase.co", "publishable": "sb_publishable_x", "secret": ""})
    monkeypatch.setattr(bulut, "istemci", lambda yazma=False: _SahteSupabase())
    assert isinstance(depo_modulu.depo_al(), depo_modulu.SupabaseDepo)
