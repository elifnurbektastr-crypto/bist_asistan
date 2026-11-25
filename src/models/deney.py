"""Gerçek veriyle walk-forward deneyi çalıştırır ve sonuçları kaydeder.

Kullanım:
  python -m src.models.deney                       # tüm modeller, yön hedefi
  python -m src.models.deney --modeller lightgbm lojistik
Tahminler data/model/tahminler.parquet dosyasına yazılır (backtest de bunu kullanır).
"""

import argparse
import logging
import time
from unittest.mock import patch

import pandas as pd

from src import config
from src.data import cache, fetch
from src.features.indicators import veri_seti_olustur
from src.models import evaluate, train

MIN_GECMIS_YIL = 5


def onbellekten_veri() -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Önbellekteki veriyi internete gitmeden okur (temizlik + elle düzeltmeler dahil)."""
    semboller = [config.yf_sembol(h) for h in config.hisse_evreni()] + [config.ENDEKS, config.USDTRY]
    with patch.object(fetch, "_indir", lambda s, b: {}):
        veri = fetch.fiyat_verisi(semboller)
    endeks, kur = veri.pop(config.ENDEKS), veri.pop(config.USDTRY, None)
    return veri, endeks, kur, cache.oku("evds", "makro")


def model_evreni(veri: dict[str, pd.DataFrame], min_yil: int = MIN_GECMIS_YIL) -> dict[str, pd.DataFrame]:
    """En az `min_yil` yıllık geçmişi olan hisseler.

    Not: Bu seçim bugünün bilgisiyle yapılıyor (bugün listede olan ve yeterince eski hisseler);
    survivorship bias olarak raporlanır.
    """
    return {s: df for s, df in veri.items() if (df.index[-1] - df.index[0]).days >= min_yil * 365}


def veri_seti() -> pd.DataFrame:
    """Model için özellik + hedef tablosunu hazırlar."""
    veri, endeks, kur, makro = onbellekten_veri()
    return veri_seti_olustur(model_evreni(veri), endeks, kur, makro)


def main() -> None:
    """Deneyi çalıştırır, özet tabloları basar, tahminleri kaydeder."""
    ayr = argparse.ArgumentParser(description=__doc__)
    ayr.add_argument("--modeller", nargs="+", default=list(train.MODELLER))
    ayr.add_argument("--cikti", default="tahminler")
    arg = ayr.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    tablo = veri_seti()
    print(f"Veri seti: {len(tablo):,} satır, {tablo.index.get_level_values('kod').nunique()} hisse")
    tahminler = []
    for ad in arg.modeller:
        bas = time.time()
        tahminler.append(train.walk_forward(tablo, [ad]))
        print(f"  {ad}: {time.time() - bas:.0f} sn")
    tahminler = pd.concat(tahminler)
    cache.yaz(tahminler, arg.cikti, "model")

    with pd.option_context("display.width", 200, "display.float_format", "{:.4f}".format):
        ozet = evaluate.ozet_tablo(tahminler)
        print("\n=== Tüm test yılları (2019-2026) ===")
        print(ozet)
        print("\n=== Yıllara göre doğruluk ===")
        print(evaluate.yillik_tablo(tahminler, "dogruluk"))
        print("\n=== Yıllara göre AUC ===")
        print(evaluate.yillik_tablo(tahminler, "auc"))
        alarm = evaluate.asiri_ogrenme_alarmi(ozet)
        print("\nAşırı öğrenme alarmı:", alarm or "yok")


if __name__ == "__main__":
    main()
