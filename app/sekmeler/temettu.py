"""Temettü sekmesi: filtrelenebilir tablo, en yüksek verimliler, hisse bazında ödeme geçmişi."""

import plotly.graph_objects as go
import streamlit as st

from app import ortak
from src import config
from src.data import dividends


def goster() -> None:
    tablo = ortak.temettu_tablosu()
    st.caption("Tutarlar **brüt** ve hisse başınadır (stopaj düşülmemiştir). Son 12 ay verimi, bedelsiz "
               "bölünmeler dikkate alınarak bugünkü hisse sayısı bazında hesaplanır.")

    c1, c2, c3, c4 = st.columns(4)
    min_verim = c1.slider("En az verim (son 12 ay)", 0.0, 20.0, 0.0, 0.5, format="%.1f%%") / 100
    min_tl = c2.number_input("En az TL (hisse başı, 12 ay)", 0.0, value=0.0, step=0.5)
    min_yil = c3.slider("En az kesintisiz yıl", 0, 12, 0)
    yaklasan_var = "durum" in tablo
    gun = c4.number_input("Hak kullanımı önümüzdeki … gün", 0, 365, 0, disabled=not yaklasan_var,
                          help="0 = filtre yok" if yaklasan_var else "Yaklaşan tarihler henüz güncellenmedi.")

    secili = dividends.filtrele(tablo, min_verim=min_verim or None, min_tl=min_tl or None,
                                min_kesintisiz_yil=min_yil or None, gun_icinde=gun or None)
    secili = secili.sort_values("son12ay_verim", ascending=False)
    st.markdown(f"**{len(secili)} hisse** filtreye uyuyor.")

    sutunlar = {
        "son_fiyat": st.column_config.NumberColumn("Son fiyat (₺)", format="%.2f"),
        "son12ay_verim": st.column_config.NumberColumn("Verim (12 ay)", format="percent"),
        "son12ay_tl": st.column_config.NumberColumn("TL (12 ay, bugünkü baz)", format="%.2f"),
        "son_temettu_tl": st.column_config.NumberColumn("Son ödeme (₺)", format="%.2f"),
        "son_temettu_tarihi": st.column_config.DateColumn("Son ödeme tarihi", format="DD.MM.YYYY"),
        "son12ay_odeme_sayisi": st.column_config.NumberColumn("Ödeme sayısı (12 ay)"),
        "kesintisiz_yil": st.column_config.NumberColumn("Kesintisiz yıl"),
    }
    if yaklasan_var:
        sutunlar.update({
            "hak_kullanim_tarihi": st.column_config.DateColumn("Sonraki hak kullanımı*", format="DD.MM.YYYY"),
            "kalan_gun": st.column_config.NumberColumn("Kalan gün"),
            "durum": st.column_config.TextColumn("Durum"),
        })
    st.dataframe(secili, column_config=sutunlar, width="stretch", height=380)
    if yaklasan_var:
        st.caption("*Yaklaşan tarihler Yahoo Finance'ten gelir ve **doğrulanmamıştır**; resmi kaynak KAP'tır.")
    else:
        st.info("Yaklaşan hak kullanım tarihleri henüz güncellenmedi.", icon="ℹ️")

    ilk = secili[secili["son12ay_verim"] > 0].head(15).iloc[::-1]
    if len(ilk):
        fig = go.Figure(go.Bar(
            x=ilk["son12ay_verim"], y=ilk.index, orientation="h", marker_color=ortak.RENKLER[0],
            text=[f"%{v * 100:.1f} · {tl:.2f} ₺" for v, tl in zip(ilk["son12ay_verim"], ilk["son12ay_tl"])],
            textposition="outside", cliponaxis=False, hovertemplate="%{y}: %{x:.1%}<extra></extra>"))
        ortak.tema(fig, "Temettü verimi en yüksek hisseler (filtreye göre)", yukseklik=60 + 28 * len(ilk))
        # Etiketler çubuğun sağına yazılır: en uzun çubuğun etiketi sığsın diye eksen %45 uzatılır
        fig.update_xaxes(tickformat=".0%", gridcolor=ortak.IZGARA, showgrid=True,
                         range=[0, float(ilk["son12ay_verim"].max()) * 1.45])
        fig.update_yaxes(showgrid=False)
        fig.update_layout(hovermode="closest")
        ortak.ciz(fig, width="stretch")

    st.subheader("Hisse bazında ödeme geçmişi")
    sol, sag = st.columns([1, 1])
    kod = sol.selectbox("Hisse", ortak.kodlar(), index=ortak.kodlar().index("FROTO"), key="temettu_kod")
    lot = sag.number_input("Elinizdeki hisse adedi (hesap için)", 0, value=100, step=10)
    gecmis = dividends.temettu_gecmisi(ortak.piyasa_verisi()["veri"][config.yf_sembol(kod)]).iloc[::-1]
    if gecmis.empty:
        st.info(f"{kod} için 2015'ten bu yana kayıtlı temettü yok.")
    else:
        gecmis = gecmis.assign(adet_icin_brut=gecmis["tl_bugunku"] * lot)
        gecmis.index = gecmis.index.strftime("%d.%m.%Y")
        st.dataframe(gecmis, width="stretch", column_config={
            "tl": st.column_config.NumberColumn("O gün hisse başı (₺)", format="%.4f"),
            "tl_bugunku": st.column_config.NumberColumn("Bugünkü hisse bazında (₺)", format="%.4f"),
            "onceki_kapanis": st.column_config.NumberColumn("Önceki kapanış (₺)", format="%.2f"),
            "verim": st.column_config.NumberColumn("Verim", format="percent"),
            "adet_icin_brut": st.column_config.NumberColumn(f"{lot} adet için brüt (₺)*", format="%.2f"),
        })
        st.caption("*Bugünkü hisse sayınız geçmişte de aynı olsaydı (bedelsizler sonrası bazda) alacağınız brüt tutar.")
    ortak.geri_bildirim("Temettü")
