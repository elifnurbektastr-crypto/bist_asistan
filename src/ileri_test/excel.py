"""İleri test Excel raporu: kayıtlardan üretilir, sayfaları korumalıdır.

Excel yalnızca bir GÖRÜNÜMDÜR: asıl kayıt git'teki CSV dosyaları ve parmak izi zinciridir.
Excel silinse ya da değiştirilse bile `python -m src.ileri_test.gunluk --excel` ile
kayıtlardan aynen yeniden üretilir.
"""

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from src import config
from src.data import dividends
from src.features.indicators import rsi
from src.ileri_test import sonuc as sonuc_mod
from src.ileri_test.kayit import IT_DIZINI

log = logging.getLogger(__name__)
EXCEL_YOLU = IT_DIZINI / "ileri_test.xlsx"
BASLIK_DOLGU = PatternFill("solid", fgColor="DCE6F2")
YUZDE_SUTUNLARI = ("isabet", "oran", "getiri", "olasilik", "verim", "vol", "beklenti", "farki")


def hisse_bilgileri(veri: dict[str, pd.DataFrame], hisse_ozeti: pd.DataFrame) -> pd.DataFrame:
    """Her hisse için güncel bilgi kartı: fiyat, getiriler, risk, temettü, son tahmin."""
    satirlar = {}
    for sembol, df in veri.items():
        k = df["duz_kapanis"]
        getiri = lambda n: k.iloc[-1] / k.iloc[-1 - n] - 1 if len(k) > n else np.nan
        satirlar[sembol.replace(".IS", "")] = {
            "son_tarih": df.index[-1].date(), "son_fiyat_tl": df["kapanis"].iloc[-1],
            "getiri_1_hafta": getiri(5), "getiri_1_ay": getiri(21),
            "getiri_3_ay": getiri(63), "getiri_1_yil": getiri(252),
            "volatilite_20g": k.pct_change().iloc[-20:].std() * np.sqrt(252),
            "rsi_14": rsi(k).iloc[-1],
            "islem_gunu": len(df),
        }
    tablo = pd.DataFrame.from_dict(satirlar, orient="index")
    tem = dividends.temettu_ozeti(veri)
    if len(tem):
        tablo = tablo.join(tem[["son12ay_verim", "son12ay_tl", "kesintisiz_yil", "son_temettu_tarihi"]]
                           .rename(columns={"son12ay_verim": "temettu_verim_12a", "son12ay_tl": "temettu_tl_12a"}))
    if len(hisse_ozeti):
        tablo = tablo.join(hisse_ozeti[["son_olasilik", "son_sinyal", "model_isabeti"]])
    tablo.index.name = "kod"
    return tablo.sort_index()


def _bicimlendir(ws, sifre: str | None) -> None:
    """Başlık, sütun genişliği, sayı biçimi, filtre, dondurulmuş satır ve koruma."""
    for hucre in ws[1]:
        hucre.font = Font(bold=True)
        hucre.fill = BASLIK_DOLGU
        hucre.alignment = Alignment(wrap_text=True, vertical="center")
    for i, sutun in enumerate(ws.iter_cols(min_row=1, max_row=min(ws.max_row, 200)), start=1):
        baslik = str(sutun[0].value or "")
        genislik = max(len(baslik), *(len(str(c.value)) for c in sutun[1:] if c.value is not None), 8)
        ws.column_dimensions[get_column_letter(i)].width = min(genislik + 2, 40)
        if any(a in baslik for a in YUZDE_SUTUNLARI):
            for c in sutun[1:]:
                c.number_format = "0.0%"
        elif any(k in baslik for k in ("fiyat", "acilis", "kapanis")) or baslik in ("temettu_tl_12a", "rsi_14"):
            for c in sutun[1:]:
                c.number_format = "#,##0.00"
    if ws.max_row > 1 and ws.max_column > 1:
        ws.auto_filter.ref = ws.dimensions
        ws.freeze_panes = "B2"
    ws.protection.sheet = True
    ws.protection.autoFilter = False   # korumalıyken de filtre kullanılabilsin
    ws.protection.sort = False
    if sifre:
        ws.protection.password = sifre


def excel_uret(tahminler: pd.DataFrame, veri: dict[str, pd.DataFrame], zincir: pd.DataFrame,
               sorunlar: list[str], model_bilgi: dict | None, yol: Path = EXCEL_YOLU,
               acilis_kayitlari: pd.DataFrame | None = None) -> Path:
    """Tüm sayfaları yazar. Dosya Excel'de açıksa yan dosyaya yazar."""
    load_dotenv(config.KOK_DIZIN / ".env")
    sifre = os.getenv("IT_EXCEL_SIFRE") or None

    sonuc = sonuc_mod.sonuclari_hesapla(tahminler, veri) if len(tahminler) else pd.DataFrame()
    oz = sonuc_mod.ozet(sonuc) if len(sonuc) else {}
    h_ozet = sonuc_mod.hisse_ozeti(sonuc) if len(sonuc) else pd.DataFrame()

    ozet_satirlari = [
        ("Rapor zamanı", pd.Timestamp.now(tz=config.SAAT_DILIMI).strftime("%Y-%m-%d %H:%M")),
        ("Kayıt bütünlüğü", "✓ SAĞLAM" if not sorunlar else "✗ SORUN VAR: " + " | ".join(sorunlar)),
        ("Model", f"{model_bilgi['model']} {model_bilgi['surum']} (eğitim sonu {model_bilgi['egitim_son_tarih']})"
         if model_bilgi else "dondurulmamış"),
        ("İlk / son tahmin günü", f"{oz.get('ilk_tahmin_gunu')} / {oz.get('son_tahmin_gunu')}"),
        ("Tahmin günü sayısı", oz.get("tahmin_gunu", 0)),
        ("Toplam tahmin / tamamlanan / bekleyen",
         f"{oz.get('toplam_tahmin', 0)} / {oz.get('tamamlanan', 0)} / {oz.get('bekleyen', 0)}"),
    ]
    karsilastirma = pd.DataFrame([
        ("Model isabeti (olasılık > 0,5 → yükselir)", oz.get("model_isabeti"), sonuc_mod.BEKLENTI["model_isabeti"]),
        ("'Hep yükselir' isabeti (çıta)", oz.get("hep_yukselir_isabeti"), sonuc_mod.BEKLENTI["hep_yukselir_isabeti"]),
        ("Güçlü al isabeti", oz.get("guclu_al_isabeti"), sonuc_mod.BEKLENTI["guclu_al_isabeti"]),
        ("Güçlü al ort. 5g getiri", oz.get("guclu_al_ort_getiri"), np.nan),
        ("Tüm tahminler ort. 5g getiri", oz.get("tum_ort_getiri"), np.nan),
    ], columns=["olcu", "ileri_test", "walk_forward_beklenti"])

    acilis_kayitlari = acilis_kayitlari if acilis_kayitlari is not None else pd.DataFrame()
    sayfalar = {
        "Tahminler": sonuc.sort_values(["tahmin_tarihi", "kod"], ascending=[False, True]) if len(sonuc) else sonuc,
        "Gözlemler": sonuc_mod.gozlemler(acilis_kayitlari, tahminler, veri),
        "Hisse Özeti": h_ozet.reset_index() if len(h_ozet) else h_ozet,
        "Hisse Kartı (genel bilgi)": hisse_bilgileri(veri, h_ozet).reset_index(),
        "Günlük": sonuc_mod.gunluk_ozet(sonuc).reset_index() if len(sonuc) else pd.DataFrame(),
        "Bütünlük": zincir,
    }

    hedef = yol
    try:
        if yol.exists():
            yol.unlink()
    except PermissionError:
        hedef = yol.with_name(f"{yol.stem}_{pd.Timestamp.now():%Y%m%d_%H%M}{yol.suffix}")
        log.warning("Excel açık olduğu için %s dosyasına yazılıyor.", hedef.name)

    with pd.ExcelWriter(hedef, engine="openpyxl") as yazici:
        pd.DataFrame(ozet_satirlari, columns=["bilgi", "deger"]).to_excel(yazici, sheet_name="Özet", index=False)
        karsilastirma.to_excel(yazici, sheet_name="Özet", index=False, startrow=len(ozet_satirlari) + 2)
        for ad, tablo in sayfalar.items():
            tablo = tablo.copy()
            for s in tablo.columns:   # Excel saat dilimli tarihleri kabul etmez
                if pd.api.types.is_datetime64_any_dtype(tablo[s]):
                    tablo[s] = tablo[s].dt.date
            tablo.to_excel(yazici, sheet_name=ad, index=False)
        for ws in yazici.book.worksheets:
            _bicimlendir(ws, sifre)
        ozet_ws = yazici.book["Özet"]
        for satir in ozet_ws.iter_rows(min_row=len(ozet_satirlari) + 3, max_row=len(ozet_satirlari) + 3):
            for h in satir:
                h.font = Font(bold=True)
                h.fill = BASLIK_DOLGU
        for satir in ozet_ws.iter_rows(min_row=len(ozet_satirlari) + 4, min_col=2, max_col=3):
            for h in satir:
                h.number_format = "0.0%"
    return hedef
