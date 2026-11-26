"""Grafik sekmesi: ücretsiz ve sınırsız mum grafiği, indikatörler, çizim araçları, gün içi (canlı) mumlar."""

import streamlit as st

from app import ortak
from app.bilesenler import grafik as cizim_grafigi
from src import config
from src.charting import chart

DONEMLER = {"6 ay": 126, "1 yıl": 252, "3 yıl": 756, "5 yıl": 1260, "Tümü": None}
ARALIK_SECENEKLERI = list(chart.GUN_ICI_ARALIKLAR) + list(chart.ARALIKLAR)


def _gostergeler(mobil: bool) -> tuple:
    """MA/EMA periyotları ve Bollinger/RSI/MACD seçimleri (telefonda katlanır bölümde)."""
    kap = st.expander("⚙️ Göstergeler", expanded=not mobil)
    with kap:
        c1, c2 = st.columns(2)
        ma_metin = c1.text_input("MA periyotları", "20, 50", key="grafik_ma", help="Virgülle ayırın, ör. 20, 50, 200")
        ema_metin = c2.text_input("EMA periyotları", "", key="grafik_ema", help="Virgülle ayırın, ör. 12, 26")
        g1, g2, g3 = st.columns(3)
        bb = g1.checkbox("Bollinger", key="grafik_bb")
        rsi_acik = g2.checkbox("RSI", True, key="grafik_rsi")
        macd_acik = g3.checkbox("MACD", key="grafik_macd")
    return chart.periyotlari_oku(ma_metin), chart.periyotlari_oku(ema_metin), bb, rsi_acik, macd_acik


def goster() -> None:
    p = ortak.piyasa_verisi()
    mobil = ortak.mobil_mi()
    c1, c2 = st.columns([1, 3])
    kod = c1.selectbox("Hisse", ortak.kodlar(), index=ortak.kodlar().index("THYAO"), key="grafik_kod")
    aralik = c2.radio("Zaman aralığı", ARALIK_SECENEKLERI, index=ARALIK_SECENEKLERI.index("Günlük"),
                      horizontal=True, key="grafik_aralik")
    gun_ici_secili = aralik in chart.GUN_ICI_ARALIKLAR
    donem = st.radio("Dönem", list(DONEMLER), index=1, horizontal=True, key="grafik_donem",
                     disabled=gun_ici_secili, help="Gün içi mumlarda son 5 işlem günü gösterilir.")
    ma, ema, bb, rsi_acik, macd_acik = _gostergeler(mobil)
    if len(ma) + len(ema) > chart.MAKS_CIZGI:
        st.caption(f"Okunabilirlik için aynı anda en fazla {chart.MAKS_CIZGI} ortalama çizgisi gösterilir.")

    df = ortak.gunluk_canli(p["veri"][config.yf_sembol(kod)], kod)   # bugünün mumu seans içinde oluşur
    gun_ici = None
    if gun_ici_secili:
        mumlar = ortak.canli_mumlar(kod)
        if mumlar is None or mumlar.empty:
            st.info("Gün içi veri şu an alınamadı; günlük grafik gösteriliyor.", icon="ℹ️")
            aralik = "Günlük"
        else:
            gun_ici = chart.gun_ici_ohlc(mumlar, aralik)
    sekil = chart.sekil_olustur(df, kod, "Günlük" if gun_ici is not None else aralik, DONEMLER[donem],
                                ma, ema, bb, rsi_acik, macd_acik, gun_ici=gun_ici, mobil=mobil)
    cizim_grafigi(sekil, kod, key="bist_grafik")

    son = chart.son_degerler(df)
    canli = ortak.canli_ozet(kod)
    k1, k2, k3, k4 = st.columns(4)
    if canli is not None and canli["zaman"].normalize() >= p["veri"][config.yf_sembol(kod)].index[-1]:
        k1.metric(f"Son fiyat · {canli['zaman']:%H:%M}", f"{canli['son_fiyat']:,.2f} ₺", f"{canli['degisim']:+.2%}")
    else:
        k1.metric("Kapanış", f"{son['kapanis']:,.2f} ₺")
    k2.metric("RSI (14)", f"{son['rsi_14']:.0f}",
              "aşırı alım" if son["rsi_14"] > 70 else "aşırı satım" if son["rsi_14"] < 30 else None,
              delta_color="off")
    k3.metric("MA 50'ye uzaklık", f"{son['kapanis'] / son['ma_50'] - 1:+.1%}")
    if son["ma_200"]:
        k4.metric("MA 200'e uzaklık", f"{son['kapanis'] / son['ma_200'] - 1:+.1%}")

    st.caption("**Sınırlamalar:** Fiyatlar 15 dakika gecikmelidir (gerçek zamanlı BIST verisi lisanslıdır). "
               "Seans içindeki son mum henüz kesinleşmemiştir. Fiyatlar bölünmelere göre düzeltilmiştir. "
               "Çizimler sadece **bu tarayıcıda** saklanır; başka cihaza taşımak için 'JSON indir / yükle' kullanın.")
    ortak.geri_bildirim("Grafik")
