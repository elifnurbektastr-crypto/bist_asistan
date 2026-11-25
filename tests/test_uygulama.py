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
    assert len(at.tabs) == 6
    metinler = " ".join(m.value for m in at.markdown)
    assert "filtreye uyuyor" in metinler          # temettü sekmesi
    assert at.metric, "analiz metrikleri görünmeli"
