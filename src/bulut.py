"""Bulut köprüsü: yerelde üretilen veri dosyalarını Supabase Storage'a yükler / buluttan indirir.

Neden: Buluttaki uygulama Yahoo'ya bağlanmaz (bulut sunucuları sık engelleniyor). Veriyi her akşam
yerel bilgisayar günceller ve buraya yükler; buluttaki uygulama açılışta buradan indirir.
Sadece değişen dosyalar aktarılır: 'manifest.json' her dosyanın SHA-256 parmak izini tutar.

Kullanım:  python -m src.bulut --yukle     (yerel → bulut, secret anahtar gerekir)
           python -m src.bulut --indir     (bulut → yerel; uygulama bunu kendisi yapar)
"""

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from src import config

log = logging.getLogger(__name__)
KOVA = "veri"
MANIFEST = "manifest.json"
# Uygulamanın okuduğu klasörler (ham Excel, admin veritabanı ve model dosyası buluta gitmez)
KLASORLER = ["fiyat", "makro", "model", "backtest", "temettu"]


def ayarlar() -> dict:
    """Supabase adresi ve anahtarları (.env yerelde; Streamlit Cloud'da 'Secrets' ortam değişkeni olur)."""
    load_dotenv(config.KOK_DIZIN / ".env")
    return {
        "url": os.getenv("SUPABASE_URL", "").strip(),
        "publishable": os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip(),
        "secret": os.getenv("SUPABASE_SECRET_KEY", "").strip(),
    }


def istemci(yazma: bool = False):
    """Supabase istemcisi. yazma=True ise secret anahtar şart (sadece yerel bilgisayarda)."""
    from supabase import create_client

    a = ayarlar()
    anahtar = a["secret"] if yazma else (a["secret"] or a["publishable"])
    if not a["url"] or not anahtar:
        raise RuntimeError("SUPABASE_URL ve " + ("SUPABASE_SECRET_KEY" if yazma else "bir Supabase anahtarı")
                           + " tanımlı değil.")
    return create_client(a["url"], anahtar)


def yerel_manifest(veri_dizini: Path = config.VERI_DIZINI) -> dict[str, str]:
    """Yüklenecek her dosyanın göreli yolu → SHA-256 parmak izi."""
    sonuc = {}
    for klasor in KLASORLER:
        for yol in sorted((veri_dizini / klasor).glob("*.parquet")):
            sonuc[f"{klasor}/{yol.name}"] = hashlib.sha256(yol.read_bytes()).hexdigest()
    return sonuc


def farklar(kaynak: dict[str, str], hedef: dict[str, str]) -> tuple[list[str], list[str]]:
    """Kaynaktan hedefe aktarılması gereken (yeni/değişen) ve hedeften silinmesi gereken dosyalar."""
    aktar = sorted(y for y, h in kaynak.items() if hedef.get(y) != h)
    sil = sorted(y for y in hedef if y not in kaynak)
    return aktar, sil


def _bulut_manifest(kova) -> dict[str, str]:
    try:
        return json.loads(kova.download(MANIFEST)).get("dosyalar", {})
    except Exception:   # ilk yükleme: manifest yok
        return {}


def yukle(veri_dizini: Path = config.VERI_DIZINI) -> int:
    """Değişen dosyaları buluta yükler; dönen değer yüklenen dosya sayısı."""
    kova = istemci(yazma=True).storage.from_(KOVA)
    yerel = yerel_manifest(veri_dizini)
    aktar, sil = farklar(yerel, _bulut_manifest(kova))
    for yol in aktar:
        kova.upload(yol, (veri_dizini / yol).read_bytes(),
                    {"content-type": "application/octet-stream", "upsert": "true"})
    if sil:
        kova.remove(sil)
    icerik = {"guncelleme": pd.Timestamp.now(tz=config.SAAT_DILIMI).isoformat(timespec="seconds"),
              "dosyalar": yerel}
    kova.upload(MANIFEST, json.dumps(icerik, indent=1).encode(),
                {"content-type": "application/json", "upsert": "true"})
    log.info("Buluta yüklendi: %d dosya (%d silindi, %d değişmedi).", len(aktar), len(sil), len(yerel) - len(aktar))
    return len(aktar)


def indir(veri_dizini: Path = config.VERI_DIZINI) -> str | None:
    """Buluttaki değişen dosyaları indirir. Dönen değer buluttaki son güncelleme zamanı."""
    kova = istemci().storage.from_(KOVA)
    icerik = json.loads(kova.download(MANIFEST))
    aktar, _ = farklar(icerik["dosyalar"], yerel_manifest(veri_dizini))
    for yol in aktar:
        hedef = veri_dizini / yol
        hedef.parent.mkdir(parents=True, exist_ok=True)
        veri = kova.download(yol)
        if hashlib.sha256(veri).hexdigest() != icerik["dosyalar"][yol]:
            raise RuntimeError(f"{yol} indirilirken bozuldu (parmak izi uyuşmuyor).")
        hedef.write_bytes(veri)
    log.info("Buluttan indirildi: %d dosya.", len(aktar))
    return icerik.get("guncelleme")


def bulutta_mi() -> bool:
    """Uygulama Streamlit Cloud'da mı çalışıyor? (Secrets'ta ya da .env'de BIST_BULUT = "1")"""
    ayarlar()   # .env'i yükler (ortamda zaten olan değerleri ezmez)
    return os.getenv("BIST_BULUT") == "1"


def main() -> None:
    ayr = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ayr.add_mutually_exclusive_group(required=True)
    g.add_argument("--yukle", action="store_true")
    g.add_argument("--indir", action="store_true")
    arg = ayr.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    yukle() if arg.yukle else indir()


if __name__ == "__main__":
    main()
