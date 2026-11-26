"""Sinyaller sekmesi (sadece özel kullanım): dondurulmuş modelin güncel sinyalleri ve takibi.

Ayar: SINYALLER_ACIK = "1" (.env ya da Streamlit Secrets). Uygulama herkese açılırsa bu ayar
kaldırılmalıdır: lisanssız yatırım tavsiyesi algısı (SPK) ve backtest'te modelin avantajı yok.
"""

import numpy as np
import pandas as pd
import streamlit as st

from app import ortak
from src.features.indicators import veri_seti_olustur
from src.ileri_test import kayit
from src.ileri_test import model as it_model
from src.ileri_test import sonuc as it_sonuc

SINYAL_SIRASI = ["güçlü al", "zayıf al", "al değil"]


@st.cache_resource(show_spinner="Model yükleniyor…")
def _model():
    return it_model.yukle()


@st.cache_data(ttl=900, show_spinner="Sinyaller hesaplanıyor…")
def _anlik_model_tahmini(son_tarih: pd.Timestamp) -> pd.DataFrame:
    """Kaydı henüz olmayan son kapanış günü için dondurulmuş modelle tahmin (kayda geçmez)."""
    p = ortak.piyasa_verisi()
    tablo = veri_seti_olustur(p["veri"], p["endeks"], p["kur"], p["makro"])
    gun = tablo.xs(son_tarih, level="tarih")
    gun = gun[gun["getiri_60"].notna()]
    gun.index = pd.MultiIndex.from_arrays([gun.index], names=["kod"])
    kapanis = pd.Series({s.replace(".IS", ""): df["kapanis"].iloc[-1] for s, df in p["veri"].items()})
    model, bilgi = _model()
    return it_model.tahmin_uret(model, bilgi, gun, kapanis)


@st.cache_data(ttl=900)
def _kayitli() -> pd.DataFrame:
    return kayit.tum_tahminler()


def sinyaller_acik() -> bool:
    import os
    return os.getenv("SINYALLER_ACIK", "").strip() == "1"


def goster() -> None:
    p = ortak.piyasa_verisi()
    st.warning("**Test amaçlı, yatırım tavsiyesi değildir.** Bu model backtest'te (2019-2026) maliyetler sonrası "
               "rastgele seçimi bile geçemedi. Sinyalleri modeli gerçek zamanda sınamak için izleyin.", icon="🧪")

    kayitli = _kayitli()
    son_kapanis = p["son_tarih"]
    if len(kayitli) and kayitli["tahmin_tarihi"].max() >= son_kapanis:
        tarih = kayitli["tahmin_tarihi"].max()
        tahmin = kayitli[kayitli["tahmin_tarihi"] == tarih].copy()
        kaynak = "ileri test kaydı (GitHub'da parmak izli)"
    else:
        tarih = son_kapanis
        tahmin = _anlik_model_tahmini(son_kapanis).copy()
        kaynak = "dondurulmuş modelle anında hesaplandı (henüz kayda geçmedi)"
    st.markdown(f"**{tarih:%d.%m.%Y} kapanışına göre sinyaller** · {kaynak}  \n"
                "<small>Anlamı: ertesi işlem günü açılışta alınırsa, 5 iş günü sonra kârda olma olasılığı.</small>",
                unsafe_allow_html=True)

    # Tahminden bu yana fiyat ne oldu (canlı veriyle)
    canli = ortak.toplu_canli()
    if canli is not None and len(canli):
        anlik_fiyat = ortak.anlik.anlik_tablo(canli)["son_fiyat"]
        tahmin["simdiki_fiyat"] = tahmin["kod"].map(anlik_fiyat)
        tahmin["tahminden_beri"] = tahmin["simdiki_fiyat"] / tahmin["kapanis"] - 1

    sayilar = tahmin["sinyal"].value_counts()
    k = st.columns(3)
    for kutu, s in zip(k, SINYAL_SIRASI):
        kutu.metric(s.capitalize(), int(sayilar.get(s, 0)))

    secim = st.radio("Göster", ["Güçlü al", "Tümü"] + [s.capitalize() for s in SINYAL_SIRASI[1:]],
                     horizontal=True, key="sinyal_filtre")
    goster_tablo = tahmin if secim == "Tümü" else tahmin[tahmin["sinyal"] == secim.lower()]
    goster_tablo = goster_tablo.sort_values("yukselis_olasiligi", ascending=False)
    sutunlar = ["kod", "sinyal", "yukselis_olasiligi", "kapanis"] + \
        [c for c in ["simdiki_fiyat", "tahminden_beri"] if c in goster_tablo] + ["beklenen_vol_20"]
    st.dataframe(goster_tablo[sutunlar], hide_index=True, width="stretch", column_config={
        "kod": st.column_config.TextColumn("Hisse"),
        "sinyal": st.column_config.TextColumn("Sinyal"),
        "yukselis_olasiligi": st.column_config.ProgressColumn("Olasılık", format="%.2f", min_value=0, max_value=1),
        "kapanis": st.column_config.NumberColumn("Tahmin günü (₺)", format="%.2f"),
        "simdiki_fiyat": st.column_config.NumberColumn("Şimdi (₺)", format="%.2f"),
        "tahminden_beri": st.column_config.NumberColumn("Tahminden beri", format="percent"),
        "beklenen_vol_20": st.column_config.NumberColumn("Beklenen oynaklık", format="percent"),
    })

    st.subheader("Modelin gerçek zamanlı karnesi")
    if kayitli.empty:
        st.info("İleri test kayıtları biriktikçe burada modelin gerçekleşen isabeti görünecek "
                "(her tahmin 5 iş günü sonra kesinleşir).")
    else:
        s = it_sonuc.sonuclari_hesapla(kayitli, p["veri"])
        oz = it_sonuc.ozet(s)
        c1, c2, c3 = st.columns(3)
        c1.metric("Kesinleşen tahmin", f"{oz['tamamlanan']:,}")
        c2.metric("Model isabeti", "–" if np.isnan(oz["model_isabeti"]) else f"{oz['model_isabeti']:.1%}")
        c3.metric("Güçlü al isabeti", "–" if np.isnan(oz["guclu_al_isabeti"]) else f"{oz['guclu_al_isabeti']:.1%}")
        acik = s[s["durum"] != "tamamlandı"]
        if len(acik):
            ara = acik.groupby("sinyal")["anlik_getiri"].agg(["count", "mean"]).reindex(SINYAL_SIRASI).dropna()
            ara.columns = ["Açık tahmin", "Ort. getiri (şu ana kadar)"]
            st.dataframe(ara.style.format({"Ort. getiri (şu ana kadar)": "{:+.2%}"}), width="stretch")
    ortak.geri_bildirim("Sinyaller")
