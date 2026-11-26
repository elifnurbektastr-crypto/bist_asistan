"""Backtest sekmesi: tek hisse için strateji karşılaştırması ve kayıtlı portföy sonuçları."""

import pandas as pd
import streamlit as st

from app import ortak
from src import config
from src.backtest import engine, metrics, strategies

STRATEJI_ADLARI = {"Al-ve-tut": "al_ve_tut", "MA 20/50 kesişimi": "ma_kesisim", "RSI 30/70": "rsi",
                   "ML sinyali (geçmiş, eşik 0,60)": "ml"}
METRIK_ADLARI = {"toplam_getiri": "Toplam getiri", "cagr": "Yıllık getiri (CAGR)", "cagr_usd": "Yıllık getiri (USD)",
                 "yillik_volatilite": "Yıllık volatilite", "sharpe": "Sharpe", "maks_dusus": "Maks. düşüş",
                 "islem_sayisi": "İşlem sayısı", "kazanma_orani": "Kazanma oranı", "piyasada_kalma": "Piyasada kalma"}


@st.cache_data(ttl=3600)
def _ml_olasiliklari() -> pd.DataFrame | None:
    t = ortak.onbellek_tablosu("tahminler", "model")
    if t is None:
        return None
    return t[t["model"] == "lightgbm_ince_ayar"]["olasilik"].unstack("kod")


def _tek_hisse() -> None:
    p = ortak.piyasa_verisi()
    c1, c2, c3 = st.columns([1, 2, 1])
    kod = c1.selectbox("Hisse", ortak.kodlar(), index=ortak.kodlar().index("THYAO"), key="bt_kod")
    secilen = c2.multiselect("Stratejiler", list(STRATEJI_ADLARI), default=list(STRATEJI_ADLARI)[:3], key="bt_str")
    para = c3.radio("Para birimi", ["TL", "USD"], horizontal=True, key="bt_para")
    df = p["veri"][config.yf_sembol(kod)]
    c4, c5, c6 = st.columns([2, 1, 1])
    # Varsayılan başlangıç 2019 (ML tahminlerinin başladığı yıl), ama hisse daha sonra halka arz
    # olduysa ilk işlem günü. Tarih kutusu hisse başına ayrı tutulur (önceki hissenin tarihi taşmasın).
    ilk, son = df.index[0].date(), df.index[-1].date()
    varsayilan = max(pd.Timestamp("2019-01-01").date(), ilk)
    tarih = c4.date_input("Dönem", (varsayilan, son), min_value=ilk, max_value=son, key=f"bt_tarih_{kod}")
    maliyet = c5.number_input("İşlem başı maliyet (%)", 0.0, 1.0, config.ISLEM_MALIYETI * 100, 0.05,
                              help="Komisyon %0,10 + kayma %0,05") / 100
    nakit = c6.checkbox("Nakit faiz kazansın", True, help="Piyasa dışındaki para politika faizi kadar getiri sağlar")
    if not secilen or len(tarih) != 2:
        st.info("En az bir strateji ve bir tarih aralığı seçin.")
        return

    faiz = p["makro"]["politika_faizi"].dropna() / 100 if p["makro"] is not None else None
    kur = p["kur"]["kapanis"] if p["kur"] is not None else None
    ml = _ml_olasiliklari()
    egriler, satirlar = {}, {}
    for ad in secilen:
        anahtar = STRATEJI_ADLARI[ad]
        if anahtar == "ml":
            if ml is None or kod not in ml:
                st.warning(f"{kod} için ML tahmini yok (model 5 yıldan uzun geçmişi olan 81 hisseyle eğitildi).")
                continue
            hedef = strategies.ml_sinyali(df, ml[kod], esik=0.60)
        else:
            hedef = strategies.STRATEJILER[anahtar](df)
        t = engine.backtest(df, hedef, maliyet, faiz if nakit else None, *[pd.Timestamp(x) for x in tarih])
        if t.empty:
            continue
        egri = t["sermaye"]
        if para == "USD" and kur is not None:
            k = kur.reindex(egri.index).ffill().bfill()
            egri = egri / k * k.iloc[0]
        egriler[ad] = egri - 1
        satirlar[ad] = metrics.ozet(t["strateji_getirisi"], faiz, t["pozisyon"], t["varlik_getirisi"], kur)
    if not egriler:
        return
    ortak.ciz(ortak.cizgiler(egriler, f"{kod} · birikimli getiri ({para})", yuzde=True), width="stretch")
    tablo = pd.DataFrame(satirlar).T.rename(columns=METRIK_ADLARI)
    yuzdeler = [c for c in tablo.columns if c not in ("Sharpe", "İşlem sayısı")]
    st.dataframe(tablo.style.format({**{c: "{:.1%}" for c in yuzdeler}, "Sharpe": "{:.2f}", "İşlem sayısı": "{:.0f}"}),
                 width="stretch")
    st.caption("Sinyal gün sonunda üretilir, işlem ertesi gün açılışında yapılır. Sharpe oranında risksiz faiz "
               "olarak politika faizi kullanılır. ML sinyali geçmiş walk-forward tahminleridir (görülmemiş veri).")


def _portfoy() -> None:
    ozet = ortak.onbellek_tablosu("portfoy_ozeti", "backtest")
    getiriler = ortak.onbellek_tablosu("portfoy_getirileri", "backtest")
    if ozet is None or getiriler is None:
        st.info("Portföy backtest sonuçları henüz üretilmedi (`python -m src.backtest.rapor`).")
        return
    st.markdown("Her 5 iş gününde bir, modelin en güçlü bulduğu **10 hisse** alınır; aynı kurallarla "
                "rastgele seçim, 81 hissenin eşit ağırlıklı portföyü ve XU100 ile karşılaştırılır. "
                "İşlem başı maliyet %0,15, nakit politika faizi kazanır.")
    st.error("**Sonuç:** ML portföyü maliyetler düşüldükten sonra eşit ağırlıklı portföyün ve rastgele seçimin "
             "gerisinde kaldı. Model sinyali bu dönemde bir avantaj sağlamadı.", icon="📉")
    egriler = (1 + getiriler.fillna(0)).cumprod()
    ortak.ciz(ortak.cizgiler({c: egriler[c] for c in egriler.columns}, "Sermaye eğrisi (TL, başlangıç = 1)",
                                   log=True, etiket=False), width="stretch")
    goster = ozet.rename(columns=METRIK_ADLARI | {"maks_dusus_usd": "Maks. düşüş (USD)",
                                                   "ort_hisse_payi": "Ort. hissede kalma",
                                                   "toplam_maliyet": "Toplam maliyet"})
    sayilar = [c for c in goster.columns if c != "Sharpe"]
    st.dataframe(goster.style.format({**{c: "{:.1%}" for c in sayilar}, "Sharpe": "{:.2f}"}, na_rep="–"),
                 width="stretch")
    yillik = (1 + getiriler).groupby(getiriler.index.year).prod() - 1
    with st.expander("Yıllık getiriler"):
        st.dataframe(yillik.style.format("{:.1%}"), width="stretch")
    st.caption("Not: 81 hisse bugünkü BIST 100'den seçildiği için eşit ağırlıklı portföy survivorship bias "
               "nedeniyle olduğundan iyi görünür; adil karşılaştırma aynı evrendeki portföyler arasındadır.")


def goster() -> None:
    mod = st.radio("Görünüm", ["Tek hisse", "Model portföyü (sonuçlar)"], horizontal=True, key="bt_mod")
    _tek_hisse() if mod == "Tek hisse" else _portfoy()
    ortak.geri_bildirim("Backtest")
