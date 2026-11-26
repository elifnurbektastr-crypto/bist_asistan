"""Streamlit özel bileşenleri."""

import shutil
from pathlib import Path

import plotly
import streamlit.components.v1 as components

_GRAFIK_DIZINI = Path(__file__).parent / "grafik"


def _plotly_js_hazirla() -> None:
    """Plotly.js'i Python paketinden bileşen klasörüne kopyalar (CDN yok, git'e girmez)."""
    hedef = _GRAFIK_DIZINI / "plotly.min.js"
    kaynak = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
    if not hedef.exists() or hedef.stat().st_size != kaynak.stat().st_size:
        shutil.copyfile(kaynak, hedef)


_plotly_js_hazirla()
_grafik = components.declare_component("bist_grafik", path=str(_GRAFIK_DIZINI))


def grafik(sekil: dict, kod: str, key: str | None = None, koyu: bool = False) -> None:
    """Çizim araçlı mum grafiği. Çizimler kullanıcının tarayıcısında hisse bazında saklanır."""
    _grafik(sekil=sekil, kod=kod, koyu=koyu, key=key, default=None)
