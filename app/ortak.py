"""Sekmelerin ortak kullandığı parçalar: veri yükleme (önbellekli), grafik teması, duyuru, geri bildirim."""

import math
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from src import config  # noqa: E402
from src.data import cache, dividends  # noqa: E402
from src.depo import NOT_SINIRI, depo_al  # noqa: E402
from src.models import deney  # noqa: E402

# Grafik renkleri: sabit sıra (bir seri her grafikte aynı rengi alır), açık zemin
RENKLER = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
METIN, IKINCIL, IZGARA, ZEMIN = "#0b0b0b", "#52514e", "#ebeae6", "#fcfcfb"

YASAL_UYARI = ("Bu uygulama eğitim ve portföy amaçlıdır; **yatırım tavsiyesi değildir**. "
               "Veriler gecikmelidir ve hata içerebilir. Geçmiş performans gelecek sonuçların garantisi değildir.")


# ---------------------------------------------------------------------------
# Veri (internete gitmez; veriyi admin tarafı günceller)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner="Veri yükleniyor…")
def piyasa_verisi() -> dict:
    """Hisseler, endeks, kur ve makro veri (sadece önbellekten)."""
    veri, endeks, kur, makro = deney.onbellekten_veri()
    return {"veri": veri, "endeks": endeks, "kur": kur, "makro": makro,
            "son_tarih": max(df.index[-1] for df in veri.values())}


@st.cache_data(ttl=3600)
def temettu_tablosu() -> pd.DataFrame:
    """Temettü özeti + (varsa) yaklaşan hak kullanım tarihleri."""
    p = piyasa_verisi()
    ozet = dividends.temettu_ozeti(p["veri"], p["son_tarih"])
    yaklasan = cache.oku("yaklasan", "temettu")
    if yaklasan is not None:
        ozet = ozet.join(yaklasan[["hak_kullanim_tarihi", "kalan_gun", "durum"]])
    return ozet


@st.cache_data(ttl=3600)
def onbellek_tablosu(ad: str, klasor: str) -> pd.DataFrame | None:
    return cache.oku(ad, klasor)


def kodlar() -> list[str]:
    return sorted(s.replace(".IS", "") for s in piyasa_verisi()["veri"])


# ---------------------------------------------------------------------------
# Grafik
# ---------------------------------------------------------------------------

def tema(fig: go.Figure, baslik: str = "", y_baslik: str = "", yukseklik: int = 380,
         y_yuzde: bool = False) -> go.Figure:
    """Ortak sade görünüm: açık zemin, ince ızgara, üstte yatay açıklama, tek eksen."""
    fig.update_layout(
        title=dict(text=baslik, font=dict(size=15, color=METIN), x=0, xanchor="left"),
        height=yukseklik, margin=dict(l=10, r=60, t=50 if baslik else 20, b=10),
        paper_bgcolor=ZEMIN, plot_bgcolor=ZEMIN, font=dict(color=IKINCIL, size=12),
        hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, title=None),
        hoverlabel=dict(bgcolor="white", font_color=METIN),
    )
    fig.update_xaxes(showgrid=False, linecolor="#c9c8c3", ticks="outside")
    fig.update_yaxes(gridcolor=IZGARA, zeroline=False, title=y_baslik,
                     tickformat=".0%" if y_yuzde else None)
    return fig


def cizgiler(seriler: dict[str, pd.Series], baslik: str, y_baslik: str = "", log: bool = False,
             yuzde: bool = False, etiket: bool = True) -> go.Figure:
    """Birden çok çizgi; her serinin sonuna değer etiketi (en fazla 4 seride)."""
    fig = go.Figure()
    for i, (ad, s) in enumerate(seriler.items()):
        s = s.dropna()
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=ad, mode="lines",
                                 line=dict(color=RENKLER[i % len(RENKLER)], width=2),
                                 hovertemplate="%{y:.1%}" if yuzde else "%{y:,.2f}"))
        if etiket and len(seriler) <= 4 and len(s):
            # Log eksende plotly açıklama konumunu log10 cinsinden ister
            y = math.log10(max(s.iloc[-1], 1e-9)) if log else s.iloc[-1]
            fig.add_annotation(x=s.index[-1], y=y, text=f"{s.iloc[-1]:.0%}" if yuzde else f"{s.iloc[-1]:,.0f}",
                               showarrow=False, xanchor="left", xshift=6, font=dict(color=METIN, size=11))
    tema(fig, baslik, y_baslik, y_yuzde=yuzde)
    if log:
        fig.update_yaxes(type="log")
    return fig


# ---------------------------------------------------------------------------
# Duyuru, geri bildirim, uyarı
# ---------------------------------------------------------------------------

def duyurular() -> None:
    """Admin'in yayınladığı aktif duyuruları sayfanın üstünde gösterir."""
    try:
        tablo = depo_al().aktif_duyurular()
    except Exception:   # depo erişilemezse uygulama çalışmaya devam etsin
        return
    for _, d in tablo.iterrows():
        metin = f"**{d['baslik']}** — {d['metin']}"
        {"onemli": st.error, "uyari": st.warning}.get(d["tur"], st.info)(metin, icon="📢")


def geri_bildirim(sekme: str) -> None:
    """Sekme altında kısa geri bildirim: 👍/👎 ve en fazla 200 karakter not (oturum başına bir kez)."""
    anahtar = f"gb_gonderildi_{sekme}"
    st.divider()
    if st.session_state.get(anahtar):
        st.caption("Geri bildiriminiz için teşekkürler 🙏")
        return
    sol, sag = st.columns([1, 4])
    with sol:
        st.caption("Bu sekme işinize yaradı mı?")
        puan = st.feedback("thumbs", key=f"gb_puan_{sekme}")
    with sag:
        notu = st.text_input("Kısa not (isteğe bağlı)", max_chars=NOT_SINIRI, key=f"gb_not_{sekme}",
                             placeholder="Ör. şu filtre de olsa iyi olurdu")
    if puan is not None and st.button("Gönder", key=f"gb_gonder_{sekme}"):
        try:
            depo_al().geri_bildirim_ekle(sekme, 1 if puan == 1 else -1, notu)
            st.session_state[anahtar] = True
            st.rerun()
        except Exception:
            st.warning("Geri bildirim şu an kaydedilemedi.")


def kenar_cubugu() -> None:
    """Proje bilgisi, veri tarihi ve yasal uyarı."""
    p = piyasa_verisi()
    with st.sidebar:
        st.markdown("### 📈 BIST Araştırma Asistanı")
        st.caption("Veri analizi · makine öğrenmesi · backtest · grafik aracı")
        st.markdown(f"**Son veri:** {p['son_tarih']:%d.%m.%Y}  \n**Hisse:** {len(p['veri'])} (BIST 100)")
        st.caption("Kaynaklar: Yahoo Finance (gecikmeli), TCMB EVDS")
        st.warning(YASAL_UYARI, icon="⚠️")
