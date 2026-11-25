"""Parquet tabanlı yerel önbellek: veriyi her seferinde yeniden indirmemek için."""

from pathlib import Path

import pandas as pd

from src.config import VERI_DIZINI


def _dosya_yolu(ad: str, klasor: str, dizin: Path | None = None) -> Path:
    """Önbellek dosyasının yolunu üretir (ör. data/fiyat/THYAO.IS.parquet)."""
    guvenli_ad = ad.replace("=", "_").replace("/", "_")
    return (dizin or VERI_DIZINI) / klasor / f"{guvenli_ad}.parquet"


def oku(ad: str, klasor: str = "fiyat", dizin: Path | None = None) -> pd.DataFrame | None:
    """Önbellekteki tabloyu okur; yoksa None döner."""
    yol = _dosya_yolu(ad, klasor, dizin)
    if not yol.exists():
        return None
    return pd.read_parquet(yol)


def yaz(df: pd.DataFrame, ad: str, klasor: str = "fiyat", dizin: Path | None = None) -> Path:
    """Tabloyu önbelleğe yazar ve dosya yolunu döner."""
    yol = _dosya_yolu(ad, klasor, dizin)
    yol.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(yol)
    return yol


def guncelleme_tarihi(ad: str, klasor: str = "fiyat", dizin: Path | None = None) -> pd.Timestamp | None:
    """Önbellek dosyasının son yazılma zamanını döner; dosya yoksa None."""
    yol = _dosya_yolu(ad, klasor, dizin)
    if not yol.exists():
        return None
    return pd.Timestamp(yol.stat().st_mtime, unit="s", tz="UTC")
