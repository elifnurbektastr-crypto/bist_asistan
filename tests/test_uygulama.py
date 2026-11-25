"""Streamlit uygulamasının duman testi: tüm sekmeler hatasız çalışıyor mu? (gerçek önbellek verisiyle)"""

import pytest
from streamlit.testing.v1 import AppTest

from src import config


@pytest.mark.skipif(not (config.VERI_DIZINI / "fiyat" / "THYAO.IS.parquet").exists(),
                    reason="önbellekte veri yok")
def test_uygulama_hatasiz_acilir():
    at = AppTest.from_file(str(config.KOK_DIZIN / "app" / "streamlit_app.py"), default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.tabs) == 5
    metinler = " ".join(m.value for m in at.markdown)
    assert "filtreye uyuyor" in metinler          # temettü sekmesi
    assert at.metric, "analiz metrikleri görünmeli"


def _admin(monkeypatch, yerel: bool) -> AppTest:
    if yerel:
        monkeypatch.setenv("BIST_ADMIN_YEREL", "1")
    else:
        monkeypatch.delenv("BIST_ADMIN_YEREL", raising=False)
    return AppTest.from_file(str(config.KOK_DIZIN / "app" / "admin_app.py"), default_timeout=120)


def test_admin_betik_olmadan_kapali(monkeypatch):
    at = _admin(monkeypatch, yerel=False)
    at.run()
    assert at.error and "sadece yerel" in at.error[0].value
    assert not at.sidebar.radio


@pytest.mark.skipif(not (config.VERI_DIZINI / "fiyat" / "THYAO.IS.parquet").exists(),
                    reason="önbellekte veri yok")
def test_admin_tum_sayfalar_hatasiz(monkeypatch):
    at = _admin(monkeypatch, yerel=True)
    at.run()
    for sayfa in at.sidebar.radio[0].options:
        at.sidebar.radio[0].set_value(sayfa).run()
        assert not at.exception, (sayfa, [e.value for e in at.exception])


@pytest.mark.yavas
@pytest.mark.skipif(not (config.VERI_DIZINI / "fiyat" / "THYAO.IS.parquet").exists(),
                    reason="önbellekte veri yok")
def test_her_hisse_tum_sekmelerde_hatasiz():
    """Hisse seçen her kutuya listedeki HER hisse verilir (kısa geçmişli yeni halka arzlar dahil)."""
    at = AppTest.from_file(str(config.KOK_DIZIN / "app" / "streamlit_app.py"), default_timeout=300)
    at.run()
    kodlar = at.selectbox(key="analiz_kod").options
    for kutu in ["grafik_kod", "analiz_kod", "temettu_kod", "bt_kod"]:
        for kod in kodlar:
            at.selectbox(key=kutu).set_value(kod).run()
            assert not at.exception, (kutu, kod, [e.value for e in at.exception])
