"""Aşama 3 backtest raporu: hisse bazlı stratejiler + ML portföyü, TL/USD, maliyet duyarlılığı.

Kullanım: python -m src.backtest.rapor
Dönem: ML tahminlerinin olduğu walk-forward test dönemi (2019 →), tüm stratejiler aynı dönemde.
Sonuçlar data/backtest/ altına kaydedilir.
"""

import numpy as np
import pandas as pd

from src import config
from src.backtest import engine, metrics, strategies
from src.data import cache
from src.models import deney

ML_MODEL = "lightgbm_ince_ayar"
PORTFOY_N = 10
RASTGELE_TEKRAR = 20
MALIYETLER = [0.0, 0.001, 0.0015, 0.002, 0.003]


def hazirla() -> dict:
    """Backtest için gereken her şeyi önbellekten yükler."""
    veri, endeks, kur, makro = deney.onbellekten_veri()
    veri = deney.model_evreni(veri)
    tahmin = cache.oku("tahminler", "model")
    tahmin = tahmin[tahmin["model"] == ML_MODEL]["olasilik"].unstack("kod")
    vol = cache.oku("tahminler_vol", "model")
    vol = vol[vol["model"] == "vol_lightgbm"]["tahmin"].unstack("kod")
    faiz = makro["politika_faizi"].dropna() / 100 if makro is not None else None
    return {"veri": veri, "endeks": endeks, "usdtry": kur["kapanis"], "olasilik": tahmin, "vol": vol,
            "faiz": faiz, "baslangic": tahmin.index.min(), "bitis": tahmin.index.max()}


def hisse_bazli(h: dict, nakit_faizi=True) -> pd.DataFrame:
    """Her hisse × strateji için metrikler (uzun tablo)."""
    faiz = h["faiz"] if nakit_faizi else None
    satirlar = []
    for sembol, df in h["veri"].items():
        kod = sembol.replace(".IS", "")
        hedefler = {ad: fn(df) for ad, fn in strategies.STRATEJILER.items()}
        if kod in h["olasilik"]:
            for esik in (0.5, 0.6):
                hedefler[f"ml_{esik:.2f}"] = strategies.ml_sinyali(df, h["olasilik"][kod], esik)
        for ad, hedef in hedefler.items():
            t = engine.backtest(df, hedef, nakit_faizi=faiz, baslangic=h["baslangic"], bitis=h["bitis"])
            if len(t) < 252:
                continue
            m = metrics.ozet(t["strateji_getirisi"], h["faiz"], t["pozisyon"], t["varlik_getirisi"], h["usdtry"])
            satirlar.append({"kod": kod, "strateji": ad, **m.to_dict()})
    return pd.DataFrame(satirlar)


def hisse_bazli_ozet(tablo: pd.DataFrame) -> pd.DataFrame:
    """Strateji başına medyan metrikler ve al-ve-tut'u geçen hisse oranı."""
    aot = tablo[tablo["strateji"] == "al_ve_tut"].set_index("kod")["cagr"]
    tablo = tablo.assign(aot_gecti=tablo["cagr"].values > aot.reindex(tablo["kod"]).values)
    ozet = tablo.groupby("strateji").agg(
        hisse=("kod", "nunique"), medyan_cagr=("cagr", "median"), medyan_cagr_usd=("cagr_usd", "median"),
        medyan_sharpe=("sharpe", "median"), medyan_maks_dusus=("maks_dusus", "median"),
        medyan_islem=("islem_sayisi", "median"), medyan_kazanma=("kazanma_orani", "median"),
        piyasada_kalma=("piyasada_kalma", "median"), aot_gecen_oran=("aot_gecti", "mean"))
    return ozet.sort_values("medyan_cagr", ascending=False)


def portfoyler(h: dict, nakit_faizi=True, maliyet=config.ISLEM_MALIYETI) -> dict[str, pd.DataFrame]:
    """ML portföyleri ve karşılaştırma ölçütleri: günlük getiri tabloları."""
    faiz = h["faiz"] if nakit_faizi else None
    takvim = h["endeks"].loc[h["baslangic"]:h["bitis"]].index
    getiriler = engine.getiri_matrisi(h["veri"], h["endeks"].index)
    olasilik = h["olasilik"].reindex(takvim)
    ortak = dict(getiriler=getiriler, maliyet=maliyet, nakit_faizi=faiz)
    sonuc = {
        "ML ilk 10 (eşik 0,60)": engine.portfoy_backtest(olasiliklar=olasilik, esik=0.60, n=PORTFOY_N, **ortak),
        "ML ilk 10 (eşik 0,50)": engine.portfoy_backtest(olasiliklar=olasilik, esik=0.50, n=PORTFOY_N, **ortak),
        "ML ilk 10 (0,60, ters volatilite)": engine.portfoy_backtest(
            olasiliklar=olasilik, esik=0.60, n=PORTFOY_N, vol=h["vol"].reindex(takvim), **ortak),
        "Eşit ağırlık (81 hisse)": engine.portfoy_backtest(
            olasiliklar=olasilik.notna().astype(float).where(olasilik.notna()), esik=0.0, n=len(olasilik.columns), **ortak),
    }
    # Rastgele 10 hisse: aynı kurallarla ama olasılıklar rastgele (model bilgisi yok)
    rng = np.random.default_rng(0)
    rastgele = []
    for _ in range(RASTGELE_TEKRAR):
        sahte = pd.DataFrame(rng.random(olasilik.shape), index=olasilik.index, columns=olasilik.columns)
        rastgele.append(engine.portfoy_backtest(olasiliklar=sahte.where(olasilik.notna()), esik=0.0, n=PORTFOY_N,
                                                **ortak)["strateji_getirisi"])
    rastgele_ort = pd.concat(rastgele, axis=1).mean(axis=1)
    sonuc["Rastgele 10 hisse (20 tekrar ort.)"] = pd.DataFrame({"strateji_getirisi": rastgele_ort})
    xu = engine.backtest(h["endeks"], strategies.al_ve_tut(h["endeks"]), maliyet=maliyet,
                         baslangic=h["baslangic"], bitis=h["bitis"])
    sonuc["XU100 al-ve-tut"] = xu.assign(hisse_payi=1.0)
    return sonuc


def portfoy_ozeti(p: dict[str, pd.DataFrame], h: dict) -> pd.DataFrame:
    """Portföy başına metrik tablosu."""
    satirlar = {}
    for ad, t in p.items():
        m = metrics.ozet(t["strateji_getirisi"], h["faiz"], usdtry=h["usdtry"])
        if "hisse_payi" in t:
            m["ort_hisse_payi"] = t["hisse_payi"].mean()
        if "maliyet" in t:
            m["toplam_maliyet"] = t["maliyet"].sum()
        satirlar[ad] = m
    return pd.DataFrame(satirlar).T


def yillik_getiriler(p: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Portföylerin takvim yılı getirileri."""
    return pd.DataFrame({ad: (1 + t["strateji_getirisi"]).groupby(t.index.year).prod() - 1 for ad, t in p.items()})


def maliyet_duyarliligi(h: dict) -> pd.DataFrame:
    """İşlem maliyeti arttıkça ML portföyü ile eşit ağırlıklı portföyün CAGR'ı."""
    satirlar = {}
    for m in MALIYETLER:
        p = portfoyler(h, maliyet=m)
        satirlar[f"%{m * 100:.2f}"] = {ad: metrics.cagr(p[ad]["strateji_getirisi"])
                                      for ad in ["ML ilk 10 (eşik 0,60)", "ML ilk 10 (eşik 0,50)", "Eşit ağırlık (81 hisse)"]}
    return pd.DataFrame(satirlar).T.rename_axis("islem_basi_maliyet")


def main() -> None:
    h = hazirla()
    print(f"Dönem: {h['baslangic'].date()} → {h['bitis'].date()} | {len(h['veri'])} hisse | "
          f"maliyet her işlemde %{config.ISLEM_MALIYETI * 100:.2f}")
    fmt = {"display.width": 220, "display.max_columns": 20, "display.float_format": "{:.3f}".format}
    with pd.option_context(*[x for kv in fmt.items() for x in kv]):
        hb = hisse_bazli(h)
        cache.yaz(hb, "hisse_bazli", "backtest")
        print("\n=== Hisse bazlı (81 hisse, medyan; nakit faiz kazanır) ===")
        print(hisse_bazli_ozet(hb))

        for faizli in (True, False):
            p = portfoyler(h, nakit_faizi=faizli)
            print(f"\n=== Portföyler ({'nakit faiz kazanır' if faizli else 'nakit faiz KAZANMAZ'}) ===")
            ozet = portfoy_ozeti(p, h)
            print(ozet)
            if faizli:
                cache.yaz(ozet, "portfoy_ozeti", "backtest")
                cache.yaz(pd.DataFrame({ad: t["strateji_getirisi"] for ad, t in p.items()}), "portfoy_getirileri", "backtest")
                print("\n=== Yıllık getiriler ===")
                print(yillik_getiriler(p))
        print("\n=== Maliyet duyarlılığı (CAGR, nakit faizli) ===")
        print(maliyet_duyarliligi(h))


if __name__ == "__main__":
    main()
