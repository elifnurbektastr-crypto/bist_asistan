"""Hisse Analizi sekmesi: fiyat, getiriler (TL/USD/endeks), risk göstergeleri."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import ortak
from src import config
from src.backtest import metrics
from src.features.indicators import rsi

DONEMLER = {"1 ay": 21, "3 ay": 63, "1 yıl": 252, "3 yıl": 756, "5 yıl": 1260, "Tümü": None}


def goster() -> None:
    p = ortak.piyasa_verisi()
    sol, sag = st.columns([1, 2])
    kod = sol.selectbox("Hisse", ortak.kodlar(), index=ortak.kodlar().index("THYAO"), key="analiz_kod")
    donem = sag.radio("Dönem", list(DONEMLER), index=2, horizontal=True, key="analiz_donem")

    df = p["veri"][config.yf_sembol(kod)]
    n = DONEMLER[donem]
    d = df.iloc[-(n + 1):] if n else df
    kur = p["kur"]["kapanis"].reindex(d.index, method="ffill") if p["kur"] is not None else None
    getiri = d["duz_kapanis"].pct_change().dropna()

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    gunluk = df["duz_kapanis"].iloc[-1] / df["duz_kapanis"].iloc[-2] - 1
    k1.metric("Son fiyat", f"{df['kapanis'].iloc[-1]:,.2f} ₺", f"{gunluk:+.2%}")
    tl = d["duz_kapanis"].iloc[-1] / d["duz_kapanis"].iloc[0] - 1
    k2.metric(f"Getiri ({donem}, TL)", f"{tl:+.1%}")
    if kur is not None:
        usd = (d["duz_kapanis"].iloc[-1] / kur.iloc[-1]) / (d["duz_kapanis"].iloc[0] / kur.iloc[0]) - 1
        k3.metric(f"Getiri ({donem}, USD)", f"{usd:+.1%}")
    k4.metric("Yıllık volatilite", f"{getiri.std() * np.sqrt(252):.0%}")
    k5.metric("Maks. düşüş", f"{metrics.maksimum_dusus(d['duz_kapanis']):.0%}")
    k6.metric("RSI (14)", f"{rsi(df['duz_kapanis']).iloc[-1]:.0f}")

    fig = go.Figure(go.Scatter(x=d.index, y=d["kapanis"], mode="lines", name=kod,
                               line=dict(color=ortak.RENKLER[0], width=2), hovertemplate="%{y:,.2f} ₺"))
    st.plotly_chart(ortak.tema(fig, f"{kod} · kapanış fiyatı (gerçek işlem fiyatı, TL)", "TL"),
                    width="stretch")

    seriler = {f"{kod} (TL)": d["duz_kapanis"] / d["duz_kapanis"].iloc[0] - 1}
    if kur is not None:
        usd_seri = d["duz_kapanis"] / kur
        seriler[f"{kod} (USD)"] = usd_seri / usd_seri.iloc[0] - 1
    xu = p["endeks"]["duz_kapanis"].reindex(d.index).ffill()
    seriler["XU100 (TL)"] = xu / xu.iloc[0] - 1
    st.plotly_chart(ortak.cizgiler(seriler, f"Dönem getirisi · {donem} (temettü ve bölünmeler dahil)", yuzde=True),
                    width="stretch")
    st.caption("TL ve USD getirisi arasındaki fark, aynı dönemdeki kur kaybını gösterir. "
               "Yüksek enflasyon döneminde TL getirisi yanıltıcı derecede yüksek görünebilir.")

    with st.expander("Son 10 işlem günü"):
        son = df[["acilis", "yuksek", "dusuk", "kapanis", "hacim"]].tail(10).iloc[::-1]
        son.index = son.index.strftime("%d.%m.%Y")
        st.dataframe(son.style.format({"hacim": "{:,.0f}", "acilis": "{:,.2f}", "yuksek": "{:,.2f}",
                                       "dusuk": "{:,.2f}", "kapanis": "{:,.2f}"}), width="stretch")
    ortak.geri_bildirim("Hisse Analizi")
