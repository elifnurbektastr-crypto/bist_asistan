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
from app.sekmeler import analiz, backtest, model, temettu  # noqa: E402


def main() -> None:
    ortak.kenar_cubugu()
    st.title("📈 BIST Yatırım Araştırma Asistanı")
    ortak.duyurular()
    sekmeler = st.tabs(["💬 Sohbet", "🕯️ Grafik", "🔎 Hisse Analizi", "💰 Temettü", "🧪 Backtest", "🤖 Model Performansı"])
    with sekmeler[0]:
        st.info("Yapay zekâ asistanıyla sohbet yakında (Aşama 5). Asistan, aşağıdaki sekmelerdeki araçları "
                "kendisi çalıştırıp sonucu Türkçe açıklayacak.", icon="🚧")
    with sekmeler[1]:
        st.info("Ücretsiz mum grafiği ve çizim aracı yakında (Aşama 4b).", icon="🚧")
    with sekmeler[2]:
        analiz.goster()
    with sekmeler[3]:
        temettu.goster()
    with sekmeler[4]:
        backtest.goster()
    with sekmeler[5]:
        model.goster()


main()
