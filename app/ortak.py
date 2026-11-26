"""Sekmelerin ortak kullandığı parçalar: veri yükleme (önbellekli), grafik teması, duyuru, geri bildirim."""

import math
from concurrent.futures import ThreadPoolExecutor
import os
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from src import bulut, config  # noqa: E402
from src.data import anlik, cache, dividends  # noqa: E402
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

GIZLI_AYARLAR = ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "BIST_BULUT")


def _secrets_ortama_aktar() -> None:
    """Streamlit Cloud 'Secrets' değerlerini ortam değişkenlerine aktarır (src/ modülleri os.getenv okur)."""
    try:
        for ad in GIZLI_AYARLAR:
            if ad in st.secrets and not os.getenv(ad):
                os.environ[ad] = str(st.secrets[ad])
    except Exception:   # yerelde secrets.toml yoksa st.secrets hata verir; .env kullanılır
        pass


def _bulut_ayarli() -> bool:
    _secrets_ortama_aktar()
    a = bulut.ayarlar()
    return bool(a["url"] and (a["publishable"] or a["secret"]))


@st.cache_resource(ttl=900, show_spinner="Veri buluttan alınıyor…")
def bulut_verisi() -> str | None:
    """Supabase ayarlıysa (yerelde de, bulutta da) GitHub'daki günlük görevin topladığı veriyi indirir.

    Sadece değişen dosyalar iner; 15 dakikada en fazla bir kez kontrol edilir. Bilgisayarda zamanlanmış
    görev olmadığı için yerel önbellek ancak bu yolla güncel kalır.
    """
    if not _bulut_ayarli():
        return None
    try:
        return bulut.indir()
    except Exception:   # internet yoksa eldeki önbellekle devam et
        return None


@st.cache_data(ttl=900, show_spinner="Veri yükleniyor…")
def piyasa_verisi() -> dict:
    """Hisseler, endeks, kur ve makro veri (sadece önbellekten; bulutta önce Supabase'den indirilir)."""
    bulut_verisi()
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
    bulut_verisi()
    return cache.oku(ad, klasor)


def kodlar() -> list[str]:
    return sorted(s.replace(".IS", "") for s in piyasa_verisi()["veri"])


MOBIL_STIL = """
<style>
@media (max-width: 640px) {
  [data-testid="stMainBlockContainer"] { padding: 1.2rem 0.8rem 3rem; }
  h1 { font-size: 1.45rem !important; line-height: 1.25 !important; padding-top: 0.2rem !important; }
  [data-baseweb="tab"] { font-size: 0.85rem; padding: 0.4rem 0.5rem; }
  /* Metrik satırları: telefonda ikişer ikişer yan yana (Streamlit normalde hepsini alt alta dizer) */
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) {
    flex-wrap: wrap !important; gap: 0.6rem 0.8rem !important; }
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] [data-testid="stMetric"]) > [data-testid="stColumn"] {
    flex: 1 1 calc(50% - 0.8rem) !important; width: calc(50% - 0.8rem) !important; min-width: calc(50% - 0.8rem) !important; }
  [data-testid="stMetricValue"] { font-size: 1.35rem !important; }
  h2 { font-size: 1.2rem !important; } h3 { font-size: 1.05rem !important; }
  [data-testid="stMetricLabel"] p { font-size: 0.8rem !important; }
}
</style>
"""


def mobil_stil() -> None:
    """Dar ekranlar için stil kuralları (sadece ekran 640 pikselden darsa etkili olur)."""
    st.markdown(MOBIL_STIL, unsafe_allow_html=True)


def ciz(fig: go.Figure, **_) -> None:
    """Bütün Plotly grafikleri buradan çizilir. Telefonda: başlık grafiğin üstüne metin olarak alınır
    (Plotly başlığı kaydırmaz, kesilir), açıklama alta iner, yükseklik azalır, araç simgeleri gizlenir."""
    # Tarih eksenleri Türkçe sayısal biçimde (Streamlit'in Plotly'sinde Türkçe ay adları yok: "Jan 2026" yerine)
    x = getattr(fig.data[0], "x", None) if fig.data else None
    if x is not None and len(x) and pd.api.types.is_datetime64_any_dtype(pd.Series(x[:1])):
        fig.update_xaxes(tickformat="%m.%Y", hoverformat="%d.%m.%Y")
    if mobil_mi():
        baslik = fig.layout.title.text
        if baslik:
            st.markdown(f"**{baslik}**")
        fig.layout.annotations = ()   # çizgi sonu değer etiketleri dar ekranda üst üste biner
        fig.update_layout(title=None, height=min(fig.layout.height or 380, 320),
                          margin=dict(l=4, r=8, t=10, b=10), font=dict(size=11),
                          legend=dict(orientation="h", yanchor="top", y=-0.18, x=0))
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    else:
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": "hover", "displaylogo": False})


def alt_bilgi() -> None:
    """Sayfanın en altı: yasal uyarı (telefonda yan menü kapalı geldiği için burada da gösterilir)."""
    st.divider()
    st.caption("⚠️ " + YASAL_UYARI.replace("**", ""))


def mobil_mi() -> bool:
    """Tarayıcı telefon/tablet mi? (User-Agent başlığına göre; test ortamında başlık yoksa False)."""
    try:
        ua = (st.context.headers.get("User-Agent") or "").lower()
    except Exception:
        return False
    return any(k in ua for k in ("mobi", "android", "iphone", "ipad"))


# ---------------------------------------------------------------------------
# Canlı (gün içi, 15 dk gecikmeli) veri
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300, show_spinner=False)
def toplu_canli() -> pd.DataFrame | None:
    """Bütün hisselerin 5 dakikalık mumları: GitHub'daki görevin 15 dakikada bir Supabase'e koyduğu kopya."""
    if _bulut_ayarli():
        try:
            bulut.indir(klasorler=[anlik.KLASOR])
        except Exception:
            pass
    return anlik.oku()


@st.cache_resource
def _yahoo_havuzu() -> ThreadPoolExecutor:
    """Yahoo isteklerinin çalıştığı küçük iş parçacığı havuzu (sayfayı bekletmemek için)."""
    return ThreadPoolExecutor(max_workers=2, thread_name_prefix="yahoo")


@st.cache_resource
def _yahoo_durumu() -> dict:
    """Yahoo doğrudan isteği reddederse bir süre tekrar denenmez (sayfa donmasın)."""
    return {"engel_bitis": pd.Timestamp(0, tz="UTC")}


@st.cache_data(ttl=60, show_spinner=False)
def canli_mumlar(kod: str) -> pd.DataFrame | None:
    """Seçili hissenin 5 dakikalık mumları: önce Yahoo'dan doğrudan (8 sn), olmazsa toplu kopyadan."""
    durum = _yahoo_durumu()
    simdi = pd.Timestamp.now(tz="UTC")
    if simdi >= durum["engel_bitis"]:
        # yfinance engellendiğinde kendi içinde tekrar dener ve zaman aşımına uymaz (30+ sn).
        # Ayrı iş parçacığında en fazla 5 sn beklenir; sayfa donmaz, geç gelen cevap boşa gider.
        is_parcacigi = _yahoo_havuzu().submit(anlik.yahoodan_cek, [config.yf_sembol(kod)], 8)
        try:
            t = is_parcacigi.result(timeout=5)
        except Exception:
            t = pd.DataFrame()
        if len(t):
            return t
        durum["engel_bitis"] = simdi + pd.Timedelta(minutes=10)
    toplu = toplu_canli()
    if toplu is None or toplu.empty:
        return None
    t = toplu[toplu["kod"] == kod]
    return t if len(t) else None


def canli_ozet(kod: str) -> pd.Series | None:
    """Seçili hissenin son fiyatı, değişimi ve saati (anlik.anlik_tablo satırı)."""
    m = canli_mumlar(kod)
    if m is None or m.empty:
        return None
    t = anlik.anlik_tablo(m)
    return t.loc[kod] if kod in t.index else None


def canli_durum_metni() -> str:
    """Kenar çubuğu için: canlı verinin saati ya da neden olmadığı."""
    toplu = toplu_canli()
    if toplu is None or toplu.empty:
        return "**Canlı veri:** henüz yok"
    son = toplu["zaman"].max()
    simdi = pd.Timestamp.now(tz=config.SAAT_DILIMI).tz_localize(None)
    seans_acik = simdi.dayofweek < 5 and 10 <= simdi.hour < 18
    if seans_acik and simdi - son > pd.Timedelta(minutes=45):
        return f"**Canlı veri:** {son:%d.%m %H:%M} · ⚠️ gecikmiş"
    return f"**Canlı veri:** {son:%d.%m %H:%M} · 🟢 15 dk gecikmeli" if seans_acik else \
        f"**Son işlem:** {son:%d.%m %H:%M} · seans kapalı"


def gunluk_canli(df: pd.DataFrame, kod: str) -> pd.DataFrame:
    """Günlük tabloya, henüz kesinleşmemiş bugünkü (ya da en son) mumu gün içi veriden ekler.

    Sadece görüntüleme içindir; model ve backtest bu satırı görmez.
    """
    m = canli_mumlar(kod)
    if m is None:
        return df
    mum = anlik.bugunku_mum(m, kod)
    if mum is None or mum.name <= df.index[-1]:
        return df
    yeni = pd.DataFrame([mum.to_dict()], index=[mum.name])
    for s in ["acilis", "yuksek", "dusuk", "kapanis"]:
        yeni[f"duz_{s}"] = yeni[s]
    yeni["bolunme"] = 0.0
    yeni["temettu"] = yeni["temettu_duz"] = 0.0
    return pd.concat([df, yeni[df.columns.intersection(yeni.columns)]])


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
        st.markdown(f"**Kesinleşmiş kapanış:** {p['son_tarih']:%d.%m.%Y}  \n**Hisse:** {len(p['veri'])} (BIST 100)")
        st.markdown(canli_durum_metni())
        st.caption("Kaynaklar: Yahoo Finance (15 dk gecikmeli), TCMB EVDS. Gerçek zamanlı BIST verisi lisanslıdır.")
        st.warning(YASAL_UYARI, icon="⚠️")
