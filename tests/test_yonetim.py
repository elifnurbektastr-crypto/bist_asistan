"""Admin arka plan işleri: yerel erişim kontrolü, elle düzeltme doğrulama ve kaydetme, hisse evreni."""

import pandas as pd
import pytest

from src import yonetim
from tests.test_indicators import sahte_hisse

ORTAM = {yonetim.YEREL_ORTAM_DEGISKENI: "1"}


@pytest.mark.parametrize("host, ortam, beklenen", [
    ("localhost:8502", ORTAM, True),
    ("127.0.0.1:8502", ORTAM, True),
    ("[::1]:8502", ORTAM, True),
    ("bist-asistan.streamlit.app", ORTAM, False),   # internetten erişim
    ("192.168.1.20:8502", ORTAM, False),            # aynı ağdaki başka cihaz
    ("localhost:8502", {}, False),                   # başlatma betiği kullanılmamış
    (None, ORTAM, True),                             # test ortamı (başlık yok)
])
def test_yerel_mi(host, ortam, beklenen):
    assert yonetim.yerel_mi(host, ortam) == beklenen


@pytest.fixture
def veri():
    return {"AAA.IS": sahte_hisse(n=50, tohum=1)}


def test_duzeltme_dogrulama(veri):
    gun = veri["AAA.IS"].index[10].strftime("%Y-%m-%d")
    iyi = pd.DataFrame([{"kod": "aaa", "tarih": gun, "oran": 10, "aciklama": "", "kaynak": "KAP"}])
    assert yonetim.duzeltmeleri_dogrula(iyi, veri) == []
    kotu = pd.DataFrame([
        {"kod": "YOK", "tarih": gun, "oran": 2},
        {"kod": "AAA", "tarih": "2020-01-04", "oran": 2},    # cumartesi
        {"kod": "AAA", "tarih": gun, "oran": -1},
        {"kod": "AAA", "tarih": gun, "oran": 2},             # tekrar
    ])
    hatalar = yonetim.duzeltmeleri_dogrula(kotu, veri)
    assert any("listesinde yok" in h for h in hatalar)
    assert any("işlem günü değil" in h for h in hatalar)
    assert any("pozitif" in h for h in hatalar)
    assert any("iki kez" in h for h in hatalar)


def test_duzeltme_kaydet_aciklamalari_korur(tmp_path):
    yol = tmp_path / "duzeltmeler.csv"
    yol.write_text("# açıklama satırı\nkod,tarih,oran,aciklama,kaynak\n", encoding="utf-8")
    tablo = pd.DataFrame([{"kod": "ccola", "tarih": "2024-08-01", "oran": 10.0, "aciklama": "1:10", "kaynak": "KAP 123"}])
    yonetim.duzeltmeleri_kaydet(tablo, yol)
    metin = yol.read_text(encoding="utf-8")
    assert metin.startswith("# açıklama satırı\n")
    okunan = yonetim.duzeltmeleri_oku(yol)
    assert okunan.loc[0, "kod"] == "CCOLA" and okunan.loc[0, "oran"] == 10.0


def test_evren(tmp_path):
    assert yonetim.evren_dogrula(["THYAO", "GARAN"]) == ["Liste en az 10 hisse içermeli."]
    assert any("geçerli" in h for h in yonetim.evren_dogrula(["THY-AO"] + [f"AAA{i}" for i in range(10)]))
    kodlar = [f"KOD{i}" for i in range(10)] + ["kod1"]
    assert any("tekrar" in h for h in yonetim.evren_dogrula(kodlar))
    yonetim.evren_kaydet([" thyao", "GARAN", ""], tmp_path / "e.csv")
    assert pd.read_csv(tmp_path / "e.csv")["kod"].tolist() == ["GARAN", "THYAO"]


def test_komutlar_sadece_tanimli_liste():
    with pytest.raises(KeyError):
        yonetim.komut_calistir("rm -rf /")
