"""Tüm veriyi indirir/günceller ve kalite raporunu yazdırır.

Kullanım:  python -m src.data.guncelle            (önbellek + artımlı güncelleme)
           python -m src.data.guncelle --yenile   (her şeyi baştan indir)
"""

import argparse
import logging

import pandas as pd

from src import config
from src.data import dividends, fetch, quality


def main() -> None:
    """Fiyat, kur, makro ve temettü verisini günceller; özet basar."""
    ayr = argparse.ArgumentParser(description=__doc__)
    ayr.add_argument("--yenile", action="store_true", help="önbelleği yok say")
    ayr.add_argument("--evren", default="bist100", help="referans/<evren>.csv")
    arg = ayr.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    hisseler = config.hisse_evreni(arg.evren)
    semboller = [config.ENDEKS, config.USDTRY] + [config.yf_sembol(h) for h in hisseler]
    print(f"{len(hisseler)} hisse + endeks + kur indiriliyor...")
    veri = fetch.fiyat_verisi(semboller, yenile=arg.yenile)

    eksik = [s for s in semboller if s not in veri]
    print(f"Gelen: {len(veri)}/{len(semboller)}" + (f"  | Gelmeyen: {eksik}" if eksik else ""))

    takvim = veri[config.ENDEKS].index if config.ENDEKS in veri else None
    hisse_verisi = {s: df for s, df in veri.items() if s not in (config.ENDEKS, config.USDTRY)}
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print("\n--- Kalite raporu ---")
        print(quality.kalite_tablosu(hisse_verisi, takvim).drop(columns="limit_asimi_tarihleri"))
        bolunmeler = pd.concat({s: quality.bolunme_kontrolu(df) for s, df in hisse_verisi.items()})
        if len(bolunmeler):
            print("\n--- Bölünme varsayımı kontrolü (sapma ≈ 1 olmalı) ---")
            print(bolunmeler)
        print("\n--- Temettü özeti ---")
        print(dividends.temettu_ozeti(hisse_verisi).sort_values("son12ay_verim", ascending=False))

    makro = fetch.evds_verisi(yenile=arg.yenile)
    print("\nEVDS:", "atlandı (anahtar yok)" if makro is None else f"{len(makro)} satır")


if __name__ == "__main__":
    main()
