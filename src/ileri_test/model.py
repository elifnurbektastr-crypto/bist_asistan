"""İleri test modeli: bir kez eğitilir, dondurulur ve tüm ileri test boyunca değişmez.

Model dosyası büyük olduğu için git dışında (data/ileri_test/) durur; parmak izi ise
git'teki ileri_test/model_surumu.json dosyasına yazılır. Yüklenirken parmak izi
kontrol edilir: model değişmişse tahmin üretilmez.
"""

import json
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd

from src import config
from src.features.indicators import OZELLIKLER
from src.ileri_test.kayit import IT_DIZINI, dosya_hash
from src.models import predict, train

MODEL_DIZINI = config.VERI_DIZINI / "ileri_test"
SURUM_DOSYASI = IT_DIZINI / "model_surumu.json"


class ModelDegisti(Exception):
    """Model dosyasının parmak izi kayıtlı olanla uyuşmuyor."""


def dondur(tablo: pd.DataFrame, surum: str = "v1", surum_dosyasi: Path = SURUM_DOSYASI,
           model_dizini: Path = MODEL_DIZINI) -> dict:
    """Hedefi bilinen tüm geçmişle modeli eğitir, kaydeder ve parmak izini yazar.

    Zaten dondurulmuş bir model varsa hata verir (ileri test boyunca model sabit kalmalı).
    """
    if surum_dosyasi.exists():
        raise FileExistsError(f"Model zaten dondurulmuş: {surum_dosyasi}")
    son_tarih = tablo.index.get_level_values("tarih").max()
    bilinen = tablo["hedef_yon"].notna() & tablo["getiri_60"].notna()
    egitim = tablo[bilinen & (tablo["hedef_bitis_yon"] <= son_tarih)]
    ortak, ozel = train.ince_ayar_modelleri(egitim, "hedef_yon")

    vol_egitim = tablo[tablo["hedef_vol_20"].gt(0) & tablo["hedef_bitis_vol"].le(son_tarih)]
    vol = lgb.LGBMRegressor(**train.LGBM_AYARLARI)
    vol.fit(vol_egitim[OZELLIKLER], np.log(vol_egitim["hedef_vol_20"]))

    model_dizini.mkdir(parents=True, exist_ok=True)
    yol = model_dizini / f"model_{surum}.joblib"
    joblib.dump({"ortak": ortak, "ozel": ozel, "vol": vol, "ozellikler": list(OZELLIKLER)}, yol, compress=3)
    bilgi = {
        "surum": surum, "model": "lightgbm_ince_ayar", "dosya": yol.name, "sha256": dosya_hash(yol),
        "egitim_son_tarih": str(egitim.index.get_level_values("tarih").max().date()),
        "egitim_satir": int(len(egitim)), "hisseye_ozel_model": len(ozel),
        "ozellikler": list(OZELLIKLER), "guclu_sinyal_esigi": predict.GUVEN_ESIGI,
        "olusturma": pd.Timestamp.now(tz=config.SAAT_DILIMI).isoformat(timespec="seconds"),
    }
    surum_dosyasi.parent.mkdir(parents=True, exist_ok=True)
    surum_dosyasi.write_text(json.dumps(bilgi, ensure_ascii=False, indent=2), encoding="utf-8")
    return bilgi


def yukle(surum_dosyasi: Path = SURUM_DOSYASI, model_dizini: Path = MODEL_DIZINI) -> tuple[dict, dict]:
    """Dondurulmuş modeli yükler; parmak izi uyuşmazsa ModelDegisti hatası verir."""
    bilgi = json.loads(surum_dosyasi.read_text(encoding="utf-8"))
    yol = model_dizini / bilgi["dosya"]
    if dosya_hash(yol) != bilgi["sha256"]:
        raise ModelDegisti(f"{yol} değişmiş; ileri test bu modelle devam edemez.")
    return joblib.load(yol), bilgi


def tahmin_uret(model: dict, bilgi: dict, gun: pd.DataFrame, kapanis: pd.Series) -> pd.DataFrame:
    """Bir günün özellik satırlarından tahmin tablosu üretir (kayda girecek biçimde).

    kapanis: o günün ham kapanış fiyatları (index = kod), sonucu kontrol etmek için kaydedilir.
    """
    ozl = model["ozellikler"]
    if ozl != list(OZELLIKLER):
        raise ModelDegisti("Koddaki özellik listesi dondurulmuş modelinkinden farklı.")
    olasilik = train.ince_ayar_tahmin(model["ortak"], model["ozel"], gun)
    esik = bilgi["guclu_sinyal_esigi"]
    kodlar = gun.index.get_level_values("kod")
    return pd.DataFrame({
        "kod": kodlar,
        "yukselis_olasiligi": olasilik,
        "sinyal": np.where(olasilik > esik, "güçlü al", np.where(olasilik > 0.5, "zayıf al", "al değil")),
        "beklenen_vol_20": np.exp(model["vol"].predict(gun[ozl])),
        "kapanis": kapanis.reindex(kodlar).values,
        "hisseye_ozel_model": [k in model["ozel"] for k in kodlar],
    }).sort_values("kod").reset_index(drop=True)
