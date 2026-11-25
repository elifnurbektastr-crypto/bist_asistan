"""İleri test sonuçları: tahmin edilen 5 günlük getiri gerçekte ne oldu?

Kural backtest ile aynı: D akşamı tahmin, D'den sonraki ilk işlem günü açılışta giriş,
5 işlem günü sonraki açılışta çıkış (düzeltilmiş fiyatla, temettü/bölünme dahil).
"""

import numpy as np
import pandas as pd

from src.features.indicators import HEDEF_UFKU

# Walk-forward'da (2019-2026) görülen değerler: ileri test bunlarla karşılaştırılır
BEKLENTI = {"model_isabeti": 0.523, "hep_yukselir_isabeti": 0.544, "guclu_al_isabeti": 0.579}


def sonuclari_hesapla(tahminler: pd.DataFrame, veri: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Her tahmine gerçekleşen getiriyi ekler; süresi dolmayanlar 'bekliyor' kalır."""
    if tahminler.empty:
        return tahminler
    sonuc = tahminler.copy()
    for sutun in ["giris_tarihi", "cikis_tarihi"]:
        sonuc[sutun] = pd.NaT
    sonuc["gerceklesen_getiri"] = np.nan
    sonuc["gecen_gun"] = 0
    ara_sutunlar = [f"gun_{k}_getiri" for k in range(1, HEDEF_UFKU + 1)]
    for s in ara_sutunlar:
        sonuc[s] = np.nan
    for kod, grup in sonuc.groupby("kod"):
        df = veri.get(f"{kod}.IS")
        if df is None:
            continue
        idx = df.index
        for i, satir in grup.iterrows():
            giris = idx.searchsorted(satir["tahmin_tarihi"], side="right")
            cikis = giris + HEDEF_UFKU
            if giris >= len(idx):
                continue
            sonuc.at[i, "giris_tarihi"] = idx[giris]
            giris_fiyati = df["duz_acilis"].iloc[giris]
            # Ara durum: girişten sonra her günün kapanışında o ana kadarki getiri
            for k in range(1, HEDEF_UFKU + 1):
                if giris + k - 1 < len(idx):
                    sonuc.at[i, f"gun_{k}_getiri"] = df["duz_kapanis"].iloc[giris + k - 1] / giris_fiyati - 1
                    sonuc.at[i, "gecen_gun"] = k
            if cikis < len(idx):
                sonuc.at[i, "cikis_tarihi"] = idx[cikis]
                sonuc.at[i, "gerceklesen_getiri"] = df["duz_acilis"].iloc[cikis] / giris_fiyati - 1
    tamam = sonuc["gerceklesen_getiri"].notna()
    gun_metni = sonuc["gecen_gun"].astype(int).astype(str) + ". gün"
    sonuc["durum"] = np.where(tamam, "tamamlandı", np.where(sonuc["gecen_gun"] > 0, gun_metni, "giriş bekleniyor"))
    son_ara = sonuc[ara_sutunlar].ffill(axis=1).iloc[:, -1]
    sonuc["anlik_getiri"] = np.where(tamam, sonuc["gerceklesen_getiri"], son_ara)
    sonuc["gercek_yon"] = np.where(tamam, (sonuc["gerceklesen_getiri"] > 0).astype(float), np.nan)
    tahmin_yon = (sonuc["yukselis_olasiligi"] > 0.5).astype(float)
    sonuc["model_dogru"] = np.where(tamam, (tahmin_yon == sonuc["gercek_yon"]).astype(float), np.nan)
    return sonuc


def ozet(sonuc: pd.DataFrame) -> dict:
    """İleri testin genel özeti ve walk-forward beklentisiyle karşılaştırma."""
    t = sonuc[sonuc["durum"] == "tamamlandı"] if len(sonuc) else sonuc
    guclu = t[t["sinyal"] == "güçlü al"] if len(t) else t
    return {
        "ilk_tahmin_gunu": sonuc["tahmin_tarihi"].min().date() if len(sonuc) else None,
        "son_tahmin_gunu": sonuc["tahmin_tarihi"].max().date() if len(sonuc) else None,
        "tahmin_gunu": sonuc["tahmin_tarihi"].nunique() if len(sonuc) else 0,
        "toplam_tahmin": len(sonuc),
        "tamamlanan": len(t),
        "bekleyen": len(sonuc) - len(t),
        "model_isabeti": t["model_dogru"].mean() if len(t) else np.nan,
        "hep_yukselir_isabeti": t["gercek_yon"].mean() if len(t) else np.nan,
        "guclu_al_sayisi": len(guclu),
        "guclu_al_isabeti": guclu["gercek_yon"].mean() if len(guclu) else np.nan,
        "guclu_al_ort_getiri": guclu["gerceklesen_getiri"].mean() if len(guclu) else np.nan,
        "tum_ort_getiri": t["gerceklesen_getiri"].mean() if len(t) else np.nan,
    }


def hisse_ozeti(sonuc: pd.DataFrame) -> pd.DataFrame:
    """Hisse başına ileri test performansı."""
    if sonuc.empty:
        return pd.DataFrame()
    t = sonuc[sonuc["durum"] == "tamamlandı"]
    son = sonuc.sort_values("tahmin_tarihi").groupby("kod").last()
    tablo = pd.DataFrame({
        "tahmin_sayisi": sonuc.groupby("kod").size(),
        "tamamlanan": t.groupby("kod").size(),
        "model_isabeti": t.groupby("kod")["model_dogru"].mean(),
        "yukselis_orani": t.groupby("kod")["gercek_yon"].mean(),
        "guclu_al_sayisi": t[t["sinyal"] == "güçlü al"].groupby("kod").size(),
        "guclu_al_isabeti": t[t["sinyal"] == "güçlü al"].groupby("kod")["gercek_yon"].mean(),
        "ort_gerceklesen_getiri": t.groupby("kod")["gerceklesen_getiri"].mean(),
        "son_tahmin_tarihi": son["tahmin_tarihi"].dt.date,
        "son_olasilik": son["yukselis_olasiligi"],
        "son_sinyal": son["sinyal"],
    })
    for s in ["tamamlanan", "guclu_al_sayisi"]:
        tablo[s] = tablo[s].fillna(0).astype(int)
    return tablo.sort_index()


def gunluk_ozet(sonuc: pd.DataFrame) -> pd.DataFrame:
    """Tahmin günü başına özet."""
    if sonuc.empty:
        return pd.DataFrame()
    g = sonuc.groupby("tahmin_tarihi")
    return pd.DataFrame({
        "hisse": g.size(),
        "guclu_al": g.apply(lambda x: (x["sinyal"] == "güçlü al").sum()),
        "ort_olasilik": g["yukselis_olasiligi"].mean(),
        "durum": g["durum"].agg(lambda x: "tamamlandı" if (x == "tamamlandı").all() else x.iloc[0]),
        "anlik_ort_getiri": g["anlik_getiri"].mean(),
        "model_isabeti": g["model_dogru"].mean(),
        "yukselen_orani": g["gercek_yon"].mean(),
        "ort_getiri": g["gerceklesen_getiri"].mean(),
        "guclu_al_ort_getiri": g.apply(lambda x: x.loc[x["sinyal"] == "güçlü al", "gerceklesen_getiri"].mean()),
    }).sort_index(ascending=False)


def gozlemler(acilis_kayitlari: pd.DataFrame, tahminler: pd.DataFrame,
              veri: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """İleri test döneminin her günü için: sabah kaydedilen açılış, resmi açılış, akşam kapanışı.

    Sabah kaydı ile günün resmi açılışı arasında %0,5'ten büyük fark varsa işaretlenir
    (Yahoo sonradan düzeltme yapmış ya da sabah veri gecikmeli gelmiş olabilir).
    """
    parcalar = []
    if len(acilis_kayitlari):
        a = acilis_kayitlari.rename(columns={"tahmin_tarihi": "tarih", "acilis": "sabah_acilis"})
        parcalar.append(a[["tarih", "kod", "sabah_acilis", "kayit_saati"]])
    if len(tahminler):
        k = tahminler.rename(columns={"tahmin_tarihi": "tarih", "kapanis": "aksam_kapanis"})
        parcalar.append(k[["tarih", "kod", "aksam_kapanis"]])
    if not parcalar:
        return pd.DataFrame()
    tablo = parcalar[0]
    for parca in parcalar[1:]:
        tablo = tablo.merge(parca, on=["tarih", "kod"], how="outer")
    resmi = []
    for _, s in tablo.iterrows():
        df = veri.get(f"{s['kod']}.IS")
        resmi.append(df.at[s["tarih"], "acilis"] if df is not None and s["tarih"] in df.index else np.nan)
    tablo["resmi_acilis"] = resmi
    if "sabah_acilis" in tablo:
        tablo["acilis_farki"] = tablo["sabah_acilis"] / tablo["resmi_acilis"] - 1
        tablo["uyari"] = np.where(tablo["acilis_farki"].abs() > 0.005, "açılış farkı > %0,5", "")
    return tablo.sort_values(["tarih", "kod"], ascending=[False, True]).reset_index(drop=True)
