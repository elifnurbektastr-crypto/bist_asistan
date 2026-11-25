"""Grafik sekmesi: ücretsiz ve sınırsız mum grafiği, indikatörler ve çizim araçları."""

import streamlit as st

from app import ortak
from app.bilesenler import grafik as cizim_grafigi
from src import config
from src.charting import chart

DONEMLER = {"6 ay": 126, "1 yıl": 252, "3 yıl": 756, "5 yıl": 1260, "Tümü": None}


def goster() -> None:
    p = ortak.piyasa_verisi()
    c1, c2, c3 = st.columns([1, 1, 2])
    kod = c1.selectbox("Hisse", ortak.kodlar(), index=ortak.kodlar().index("THYAO"), key="grafik_kod")
    aralik = c2.radio("Zaman aralığı", list(chart.ARALIKLAR), horizontal=True, key="grafik_aralik")
    donem = c3.radio("Dönem", list(DONEMLER), index=1, horizontal=True, key="grafik_donem")

    c4, c5, c6 = st.columns([1, 1, 2])
    ma_metin = c4.text_input("MA periyotları", "20, 50", key="grafik_ma", help="Virgülle ayırın, ör. 20, 50, 200")
    ema_metin = c5.text_input("EMA periyotları", "", key="grafik_ema", help="Virgülle ayırın, ör. 12, 26")
    with c6:
        st.write("")
        g1, g2, g3 = st.columns(3)
        bb = g1.checkbox("Bollinger", key="grafik_bb")
        rsi_acik = g2.checkbox("RSI", True, key="grafik_rsi")
        macd_acik = g3.checkbox("MACD", key="grafik_macd")

    ma, ema = chart.periyotlari_oku(ma_metin), chart.periyotlari_oku(ema_metin)
    if len(ma) + len(ema) > chart.MAKS_CIZGI:
        st.caption(f"Okunabilirlik için aynı anda en fazla {chart.MAKS_CIZGI} ortalama çizgisi gösterilir.")
    df = p["veri"][config.yf_sembol(kod)]
    sekil = chart.sekil_olustur(df, kod, aralik, DONEMLER[donem], ma, ema, bb, rsi_acik, macd_acik)
    cizim_grafigi(sekil, kod, key="bist_grafik")

    son = chart.son_degerler(df)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Kapanış", f"{son['kapanis']:,.2f} ₺")
    k2.metric("RSI (14)", f"{son['rsi_14']:.0f}",
              "aşırı alım bölgesi" if son["rsi_14"] > 70 else "aşırı satım bölgesi" if son["rsi_14"] < 30 else None,
              delta_color="off")
    k3.metric("MA 50'ye uzaklık", f"{son['kapanis'] / son['ma_50'] - 1:+.1%}")
    if son["ma_200"]:
        k4.metric("MA 200'e uzaklık", f"{son['kapanis'] / son['ma_200'] - 1:+.1%}")

    st.caption("**Sınırlamalar:** Veri gecikmelidir (anlık değil, günlük kapanış). Fiyatlar bölünmelere göre "
               "düzeltilmiştir. Çizimler sadece **bu tarayıcıda** saklanır; başka cihaza taşımak için "
               "'JSON indir / yükle' kullanın. Otomatik formasyon tanıma yoktur.")
    ortak.geri_bildirim("Grafik")
