"""BIST Yatırım Araştırma Asistanı — kullanıcı arayüzü.

Çalıştırma: streamlit run app/streamlit_app.py
Veri internetten çekilmez; önbellekteki veriyi admin tarafı (yerel) günceller.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="BIST Araştırma Asistanı", page_icon="📈", layout="wide")

from app import ortak  # noqa: E402
from src import bulut  # noqa: E402
from app.sekmeler import analiz, backtest, grafik, model, sinyaller, temettu  # noqa: E402


def main() -> None:
    ortak.mobil_stil()
    ortak.kenar_cubugu()
    st.title("📈 BIST Yatırım Araştırma Asistanı")
    ortak.duyurular()
    bulut.ayarlar()   # .env'i yükler (SINYALLER_ACIK gibi ayarlar için)
    ortak.bulut_verisi()
    sayfalar = [("🕯️ Grafik", grafik), ("🔎 Hisse Analizi", analiz)]
    if sinyaller.sinyaller_acik():   # sadece özel kullanımda (Secrets/.env: SINYALLER_ACIK = "1")
        sayfalar.append(("🎯 Sinyaller", sinyaller))
    sayfalar += [("💰 Temettü", temettu), ("🧪 Backtest", backtest), ("🤖 Model Performansı", model)]
    for sekme, modul in zip(st.tabs([ad for ad, _ in sayfalar]), [m for _, m in sayfalar]):
        with sekme:
            modul.goster()
    ortak.alt_bilgi()


main()
