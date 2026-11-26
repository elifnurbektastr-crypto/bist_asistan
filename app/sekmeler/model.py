"""Model Performansı sekmesi: walk-forward ve ileri test sonuçları.

Güncel sinyaller burada GÖSTERİLMEZ (yatırım tavsiyesi algısı ve SPK düzenlemesi nedeniyle);
sadece modelin geçmişte ne kadar başarılı/başarısız olduğu gösterilir.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sklearn.metrics import roc_auc_score

from app import ortak
from src import config
from src.ileri_test import kayit
from src.ileri_test import sonuc as it_sonuc

MODEL_ADLARI = {"lightgbm_ince_ayar": "LightGBM + hisseye ince ayar", "lightgbm_grup": "LightGBM grup",
                "lightgbm": "LightGBM", "lojistik": "Lojistik regresyon", "rastgele_orman": "Random forest",
                "hep_yukselir": "Hep yükselir (çıta)", "rastgele": "Rastgele (çıta)"}


@st.cache_data(ttl=3600)
def _walk_forward_ozeti() -> tuple[pd.DataFrame, pd.DataFrame] | None:
    t = ortak.onbellek_tablosu("tahminler", "model")
    if t is None:
        return None
    t = t.assign(dogru=((t["olasilik"] > 0.5) == (t["gercek"] == 1)).astype(float))
    yillik = t.groupby(["model", "yil"])["dogru"].mean().unstack("model")
    ozet = pd.DataFrame({
        "Doğruluk": t.groupby("model")["dogru"].mean(),
        "AUC": t.groupby("model").apply(lambda g: roc_auc_score(g["gercek"], g["olasilik"])
                                        if g["olasilik"].nunique() > 1 else float("nan")),
    }).rename(index=MODEL_ADLARI).sort_values("Doğruluk", ascending=False)
    return ozet, yillik


@st.cache_data(ttl=3600)
def _ileri_test_ozeti() -> dict:
    tahminler = kayit.tum_tahminler()
    if tahminler.empty:
        return {}
    s = it_sonuc.sonuclari_hesapla(tahminler, ortak.piyasa_verisi()["veri"])
    tamam = s[s["durum"] == "tamamlandı"]   # sadece sonucu kesinleşmiş tahminler (güncel sinyal yok)
    return {"oz": it_sonuc.ozet(tamam) if len(tamam) else None, "gun": tahminler["tahmin_tarihi"].nunique(),
            "ilk": tahminler["tahmin_tarihi"].min(), "saglam": not kayit.dogrula()}


def goster() -> None:
    st.markdown("Model, bir hissenin **ertesi gün açılışından 5 iş günü sonrasına** kadar yükselip "
                "yükselmeyeceğini tahmin etmeye çalışır. Aşağıdaki sonuçların hepsi modelin eğitimde "
                "**görmediği** veriler üzerindendir (walk-forward, 2019-2026).")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Model isabeti", "%52,3", "-2,1 puan (çıtaya göre)", delta_color="normal")
    k2.metric("'Hep yükselir' çıtası", "%54,4")
    k3.metric("AUC", "0,516", help="0,5 = yazı-tura; 1 = kusursuz sıralama")
    k4.metric("Volatilite tahmini hatası", "-%21", "basit yönteme göre", delta_color="off")
    st.warning("**Dürüst özet:** Yön tahmini modeli basit 'hep yükselir' tahminini geçemedi ve backtest'te "
               "maliyetler sonrası avantaj sağlamadı. Volatilite (risk) tahmini ise her yıl basit yöntemden iyiydi.",
               icon="🧭")

    wf = _walk_forward_ozeti()
    if wf is not None:
        ozet, yillik = wf
        sol, sag = st.columns([3, 2])
        with sag:
            st.dataframe(ozet.style.format({"Doğruluk": "{:.1%}", "AUC": "{:.3f}"}, na_rep="–"),
                         width="stretch")
        with sol:
            fig = go.Figure()
            for i, m in enumerate(["lightgbm_ince_ayar", "hep_yukselir"]):
                if m in yillik:
                    fig.add_trace(go.Scatter(x=yillik.index, y=yillik[m], name=MODEL_ADLARI[m], mode="lines+markers",
                                             line=dict(color=ortak.RENKLER[i], width=2), marker=dict(size=8),
                                             hovertemplate="%{y:.1%}"))
            fig.add_hline(y=0.5, line=dict(color="#8a8984", dash="dot", width=1))
            ortak.ciz(ortak.tema(fig, "Yıllara göre isabet", y_yuzde=True), width="stretch")

    st.subheader("İleri test (gerçek zamanlı)")
    it = _ileri_test_ozeti()
    if not it:
        st.info("İleri test yeni başladı; ilk sonuçlar tahminlerin 5 iş günü dolduktan sonra görünecek.")
    else:
        st.markdown(f"Dondurulmuş model {it['ilk']:%d.%m.%Y} tarihinden beri her iş günü tahmin yapıyor "
                    f"(**{it['gun']} gün**). Kayıtlar SHA-256 parmak izi zinciriyle korunuyor: "
                    f"{'✓ sağlam' if it['saglam'] else '✗ sorun var'}.")
        oz = it["oz"]
        if oz is None:
            st.info("Henüz sonucu kesinleşmiş tahmin yok (her tahmin 5 iş günü sonra kesinleşir).")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Kesinleşen tahmin", f"{oz['tamamlanan']:,}")
            c2.metric("Model isabeti", f"{oz['model_isabeti']:.1%}", f"beklenti %{it_sonuc.BEKLENTI['model_isabeti'] * 100:.1f}",
                      delta_color="off")
            c3.metric("'Hep yükselir' isabeti", f"{oz['hep_yukselir_isabeti']:.1%}")
    with st.expander("Deney günlüğü (tüm denemeler ve sonuçları)"):
        st.markdown((config.KOK_DIZIN / "docs" / "deney-gunlugu.md").read_text(encoding="utf-8"))
    ortak.geri_bildirim("Model Performansı")
