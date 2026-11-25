"""Yönetici (admin) sayfası — SADECE yerel bilgisayarda çalışır, internete açılmaz.

Başlatma: powershell -File admin_baslat.ps1   (127.0.0.1:8502, BIST_ADMIN_YEREL=1)
Bu iki şart sağlanmazsa sayfa hiçbir şey göstermeden durur.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

st.set_page_config(page_title="BIST Asistan · Admin", page_icon="🛠️", layout="wide")

from app import ortak  # noqa: E402
from src import config, yonetim  # noqa: E402
from src.data import dividends, quality  # noqa: E402
from src.depo import DUYURU_TURLERI, depo_al  # noqa: E402
from src.ileri_test import kayit  # noqa: E402
from src.ileri_test import sonuc as it_sonuc  # noqa: E402

# --- Güvenlik kapısı -----------------------------------------------------------
if not yonetim.yerel_mi(st.context.headers.get("Host")):
    st.error("Bu sayfa sadece yerel bilgisayarda, başlatma betiğiyle açılabilir.")
    st.stop()

SAYFALAR = ["🏠 Durum", "📢 Duyurular", "💬 Geri bildirimler", "🎯 Güncel tahminler",
            "✏️ Elle veri girişi", "⚙️ Veri işlemleri"]


def durum() -> None:
    p = ortak.piyasa_verisi()
    zincir_t, zincir_a = kayit.zinciri_oku(), kayit.zinciri_oku(tur="acilis")
    sorunlar = kayit.dogrula()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Son fiyat verisi", f"{p['son_tarih']:%d.%m.%Y}")
    k2.metric("Son tahmin kaydı", zincir_t["tarih"].iloc[-1] if len(zincir_t) else "henüz yok")
    k3.metric("Son açılış kaydı", zincir_a["tarih"].iloc[-1] if len(zincir_a) else "henüz yok")
    k4.metric("Kayıt bütünlüğü", "✓ sağlam" if not sorunlar else f"✗ {len(sorunlar)} sorun")
    for s in sorunlar:
        st.error(s)

    st.subheader("Veri kalitesi")
    kalite = quality.kalite_tablosu(p["veri"], p["endeks"].index)
    supheli = kalite[kalite["supheli_sicrama"] > 0]
    eski = kalite[pd.to_datetime(kalite["son_tarih"]) < p["son_tarih"]]
    c1, c2 = st.columns(2)
    c1.metric("Düzeltilmemiş şüpheli sıçrama (>%35)", int(kalite["supheli_sicrama"].sum()))
    c2.metric("Güncel olmayan hisse", len(eski))
    if len(supheli):
        st.warning("Şüpheli sıçrama var: 'Elle veri girişi' sayfasından KAP oranını girin.")
        st.dataframe(supheli[["supheli_sicrama", "son_tarih"]], use_container_width=True)
    if len(eski):
        st.warning(f"Güncel olmayan hisseler: {', '.join(i.replace('.IS', '') for i in eski.index)}")

    st.subheader("Otomatik görev günlüğü (son satırlar)")
    st.code(yonetim.log_sonu(config.VERI_DIZINI / "ileri_test.log") or "henüz kayıt yok", language=None)


def duyurular() -> None:
    depo = depo_al()
    with st.form("yeni_duyuru", clear_on_submit=True):
        st.markdown("**Yeni duyuru**")
        baslik = st.text_input("Başlık", max_chars=80)
        metin = st.text_area("Metin", max_chars=500)
        c1, c2 = st.columns(2)
        tur = c1.selectbox("Tür", DUYURU_TURLERI, format_func={"bilgi": "Bilgi (mavi)", "uyari": "Uyarı (sarı)",
                                                                "onemli": "Önemli (kırmızı)"}.get)
        bitis = c2.date_input("Bitiş tarihi (isteğe bağlı)", value=None)
        if st.form_submit_button("Yayınla"):
            try:
                depo.duyuru_ekle(baslik, metin, tur, bitis.strftime("%Y-%m-%d") if bitis else None)
                st.success("Duyuru yayınlandı; kullanıcı sayfasında hemen görünür.")
            except ValueError as hata:
                st.error(str(hata))
    st.markdown("**Tüm duyurular**")
    tablo = depo.tum_duyurular()
    if tablo.empty:
        st.info("Henüz duyuru yok.")
    for _, d in tablo.iterrows():
        c1, c2 = st.columns([6, 1])
        durum_metni = "🟢 aktif" if d["aktif"] else "⚪ kapalı"
        c1.markdown(f"{durum_metni} · **{d['baslik']}** — {d['metin']}  \n"
                    f"<small>{d['tur']} · {d['olusturma'][:16]} · bitiş: {d['bitis'] or '—'}</small>",
                    unsafe_allow_html=False)
        if d["aktif"] and c2.button("Kapat", key=f"kapat_{d['id']}"):
            depo.duyuru_kapat(d["id"])
            st.rerun()


def geri_bildirimler() -> None:
    gb = depo_al().geri_bildirimler()
    if gb.empty:
        st.info("Henüz geri bildirim yok.")
        return
    ozet = gb.groupby("sekme")["puan"].agg(begeni=lambda x: (x > 0).sum(), begenmeme=lambda x: (x < 0).sum())
    fig = go.Figure([
        go.Bar(name="👍", y=ozet.index, x=ozet["begeni"], orientation="h", marker_color=ortak.RENKLER[0]),
        go.Bar(name="👎", y=ozet.index, x=ozet["begenmeme"], orientation="h", marker_color=ortak.RENKLER[1]),
    ])
    fig.update_layout(barmode="group", hovermode="closest")
    st.plotly_chart(ortak.tema(fig, "Sekme bazında geri bildirim", yukseklik=120 + 50 * len(ozet)),
                    use_container_width=True)
    sekme = st.selectbox("Sekme", ["Tümü"] + sorted(gb["sekme"].unique()))
    sadece_notlu = st.checkbox("Sadece not yazılanlar", True)
    goster = gb if sekme == "Tümü" else gb[gb["sekme"] == sekme]
    if sadece_notlu:
        goster = goster[goster["notu"].notna()]
    st.dataframe(goster.assign(puan=goster["puan"].map({1: "👍", -1: "👎"})),
                 use_container_width=True, hide_index=True)


def guncel_tahminler() -> None:
    st.warning("Bu sayfa sadece sizin içindir. Backtest modelin maliyet sonrası avantajı olmadığını gösterdi; "
               "bu tahminler yatırım kararı için kullanılmamalı.", icon="⚠️")
    tahminler = kayit.tum_tahminler()
    if tahminler.empty:
        st.info("İleri testte henüz tahmin yok (her iş günü 19:00'da üretilir).")
        return
    son = tahminler["tahmin_tarihi"].max()
    st.markdown(f"**Son tahmin günü:** {son:%d.%m.%Y} · model {tahminler['model_surumu'].iloc[-1]}")
    gun = tahminler[tahminler["tahmin_tarihi"] == son].sort_values("yukselis_olasiligi", ascending=False)
    st.dataframe(gun.drop(columns=["tahmin_tarihi", "model_surumu"]), use_container_width=True, hide_index=True,
                 column_config={"yukselis_olasiligi": st.column_config.ProgressColumn(
                     "Yükseliş olasılığı", format="%.3f", min_value=0, max_value=1),
                     "beklenen_vol_20": st.column_config.NumberColumn("Beklenen vol (20g)", format="percent"),
                     "kapanis": st.column_config.NumberColumn("Kapanış (₺)", format="%.2f")})

    st.subheader("Açık tahminlerin ara durumu")
    s = it_sonuc.sonuclari_hesapla(tahminler, ortak.piyasa_verisi()["veri"])
    acik = s[s["durum"] != "tamamlandı"]
    if acik.empty:
        st.info("Açık tahmin yok.")
    else:
        ozet = acik.groupby(["tahmin_tarihi", "sinyal"])["anlik_getiri"].agg(["count", "mean"]).unstack("sinyal")
        st.dataframe(ozet.style.format("{:.2%}", subset=[c for c in ozet.columns if c[0] == "mean"]),
                     use_container_width=True)
    st.caption("Ayrıntılı tablo: ileri_test/ileri_test.xlsx")


def elle_veri() -> None:
    p = ortak.piyasa_verisi()
    st.subheader("Sermaye artırımı düzeltmeleri")
    st.markdown("Yahoo'nun kaydetmediği ya da yanlış kaydettiği bölünme/bedelsiz/bedelli artırımlar. "
                "**Oran = 1 hissenin kaç hisse olduğu** (ör. %900 bedelsiz → 10). KAP duyurusundan doğrulayıp "
                "kaynak sütununa duyuru linkini ya da numarasını yazın.")
    tablo = yonetim.duzeltmeleri_oku()
    duzenlenen = st.data_editor(tablo, num_rows="dynamic", use_container_width=True, key="duzeltme_editor",
                                column_config={"oran": st.column_config.NumberColumn("oran", min_value=0.0, format="%.4f")})
    c1, c2 = st.columns([1, 4])
    if c1.button("Kontrol et ve kaydet", type="primary"):
        hatalar = yonetim.duzeltmeleri_dogrula(duzenlenen, p["veri"])
        if hatalar:
            for h in hatalar:
                st.error(h)
        else:
            yonetim.duzeltmeleri_kaydet(duzenlenen)
            ok, cikti = yonetim.git_kaydet([yonetim.DUZELTME_DOSYASI], "Elle veri: sermaye artırımı düzeltmeleri güncellendi")
            st.cache_data.clear()
            st.success("Kaydedildi" + (" ve git'e commit'lendi." if ok else f"; git kaydı yapılamadı: {cikti[:200]}"))
    with st.expander("Yardım: düzeltme sonrası hâlâ şüpheli görünen günler"):
        kalan = pd.concat({s.replace(".IS", ""): quality.supheli_sicramalar(df) for s, df in p["veri"].items()})
        st.dataframe(kalan, use_container_width=True) if len(kalan) else st.success("Şüpheli sıçrama kalmadı.")

    st.subheader("Hisse listesi (BIST 100)")
    st.caption("Liste değişirse yeni hisselerin verisi bir sonraki güncellemede indirilir. Dondurulmuş model "
               "yeni hisseler için ortak modeli kullanır.")
    evren = pd.read_csv(yonetim.EVREN_DOSYASI) if yonetim.EVREN_DOSYASI.exists() else pd.DataFrame({"kod": []})
    yeni_evren = st.data_editor(evren, num_rows="dynamic", use_container_width=True, key="evren_editor", height=250)
    if st.button("Listeyi kontrol et ve kaydet"):
        kodlar = yeni_evren["kod"].dropna().astype(str).tolist()
        hatalar = yonetim.evren_dogrula(kodlar)
        if hatalar:
            for h in hatalar:
                st.error(h)
        else:
            yonetim.evren_kaydet(kodlar)
            ok, _ = yonetim.git_kaydet([yonetim.EVREN_DOSYASI], "Elle veri: hisse listesi güncellendi")
            st.cache_data.clear()
            st.success(f"{len(set(kodlar))} hisse kaydedildi" + (" ve git'e commit'lendi." if ok else "."))


def veri_islemleri() -> None:
    st.markdown("Uzun süren işlemler arka planda çalışır; bitince çıktısı burada görünür.")
    for ad in yonetim.KOMUTLAR:
        if st.button(ad, key=f"komut_{ad}"):
            with st.spinner(f"{ad} çalışıyor… (birkaç dakika sürebilir)"):
                kod, cikti = yonetim.komut_calistir(ad)
            (st.success if kod == 0 else st.error)(f"Bitti (çıkış kodu {kod}).")
            st.code(cikti or "(çıktı yok)", language=None)
            st.cache_data.clear()
    if st.button("Yaklaşan temettü tarihlerini güncelle (Yahoo)"):
        with st.spinner("100 hisse için yaklaşan hak kullanım tarihleri alınıyor…"):
            t = dividends.yaklasan_temettuler(ortak.kodlar(), yenile=True)
        st.success(f"{(t['durum'] == 'yaklaşan').sum()} hissede yaklaşan tarih bulundu.")
        st.dataframe(t[t["durum"] == "yaklaşan"].sort_values("kalan_gun"), use_container_width=True)
        st.cache_data.clear()


def main() -> None:
    with st.sidebar:
        st.markdown("### 🛠️ Admin")
        st.caption("Sadece bu bilgisayarda · 127.0.0.1")
        sayfa = st.radio("Sayfa", SAYFALAR, label_visibility="collapsed")
    st.title(sayfa)
    {"🏠 Durum": durum, "📢 Duyurular": duyurular, "💬 Geri bildirimler": geri_bildirimler,
     "🎯 Güncel tahminler": guncel_tahminler, "✏️ Elle veri girişi": elle_veri,
     "⚙️ Veri işlemleri": veri_islemleri}[sayfa]()


main()
