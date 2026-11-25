"""Proje genelindeki ayarlar: hisse evreni, tarih aralığı, yollar, komisyon."""

from pathlib import Path

import pandas as pd

# --- Yollar ---
KOK_DIZIN = Path(__file__).resolve().parents[1]
VERI_DIZINI = KOK_DIZIN / "data"            # parquet önbelleği (git dışında)
REFERANS_DIZINI = KOK_DIZIN / "referans"    # hisse listeleri (git içinde)

# --- Tarih aralığı ---
BASLANGIC_TARIHI = "2015-01-01"

# --- Semboller ---
ENDEKS = "XU100.IS"      # karşılaştırma ölçütü (benchmark)
USDTRY = "USDTRY=X"      # USD/TRY kuru (yfinance; "TRY=X" ile aynı seri, o sembol sık engelleniyor)

# BIST 100 listesi gelene kadar kullanılan çekirdek liste (likit, farklı sektörler)
CEKIRDEK_HISSELER = [
    "THYAO", "GARAN", "ASELS", "BIMAS", "KCHOL",
    "AKBNK", "EREGL", "SISE", "TUPRS", "FROTO",
]

# --- Backtest ---
KOMISYON_ORANI = 0.001   # %0,1 (alım ve satımda ayrı ayrı uygulanır)

# --- Piyasa kuralları ---
GUNLUK_FIYAT_LIMITI = 0.10   # BIST pay piyasası günlük ±%10 fiyat limiti
SEANS_KAPANIS_SAATI = "18:30"  # bu saatten önce bugünün çubuğu tamamlanmamış sayılır
SAAT_DILIMI = "Europe/Istanbul"

# --- TCMB EVDS seri kodları ---
# 2026-11-25'te EVDS üzerinde doğrulandı.
# Eski TÜFE serisi (TP.FG.J0, 2003=100) Ocak 2026'da kesildi; TÜİK baz yılını 2025=100 yaptı.
EVDS_SERILERI = {
    "tufe": "TP.TUKFIY2025.GENEL",   # TÜFE genel endeks (2025=100), aylık, 2005'ten itibaren
    "politika_faizi": "TP.APIFON4",  # TCMB ağırlıklı ortalama fonlama maliyeti (%), günlük
}
EVDS_PARCA_YIL = 3   # EVDS tek istekte ~1000 satırdan fazlasını döndürmüyor


def yf_sembol(kod: str) -> str:
    """BIST kodunu yfinance sembolüne çevirir (THYAO -> THYAO.IS)."""
    kod = kod.strip().upper()
    if kod.endswith(".IS") or "=" in kod:
        return kod
    return f"{kod}.IS"


def hisse_evreni(ad: str = "bist100") -> list[str]:
    """Hisse listesini döndürür.

    `referans/<ad>.csv` varsa oradan ('kod' sütunu) okur, yoksa çekirdek listeye döner.
    """
    dosya = REFERANS_DIZINI / f"{ad}.csv"
    if dosya.exists():
        kodlar = pd.read_csv(dosya)["kod"].dropna().astype(str).str.strip().str.upper()
        return sorted(set(kodlar))
    return list(CEKIRDEK_HISSELER)
