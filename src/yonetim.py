"""Admin sayfasının arka plan işleri: elle veri doğrulama/kaydetme, git kaydı, arka plan komutları.

Admin arayüzü (app/admin_app.py) ince kalır; doğrulama ve yazma mantığı burada test edilir.
"""

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

from src import config

DUZELTME_DOSYASI = config.REFERANS_DIZINI / "duzeltmeler.csv"
EVREN_DOSYASI = config.REFERANS_DIZINI / "bist100.csv"
DUZELTME_SUTUNLARI = ["kod", "tarih", "oran", "aciklama", "kaynak"]
YEREL_ORTAM_DEGISKENI = "BIST_ADMIN_YEREL"
YEREL_HOSTLAR = ("localhost", "127.0.0.1", "[::1]")


# ---------------------------------------------------------------------------
# Güvenlik: admin sadece yerel bilgisayarda
# ---------------------------------------------------------------------------

def yerel_mi(host_basligi: str | None, ortam: dict | None = None) -> bool:
    """Admin sayfası açılabilir mi? İki şart: başlatma betiğinin ortam değişkeni ve yerel adres.

    host_basligi: tarayıcının gönderdiği Host başlığı (ör. 'localhost:8502'); test ortamında None olabilir.
    """
    ortam = os.environ if ortam is None else ortam
    if ortam.get(YEREL_ORTAM_DEGISKENI) != "1":
        return False
    if host_basligi is None:
        return True
    host = host_basligi.rsplit(":", 1)[0] if not host_basligi.startswith("[") else host_basligi.split("]")[0] + "]"
    return host in YEREL_HOSTLAR


# ---------------------------------------------------------------------------
# Elle düzeltmeler (referans/duzeltmeler.csv)
# ---------------------------------------------------------------------------

def duzeltmeleri_oku(yol: Path = DUZELTME_DOSYASI) -> pd.DataFrame:
    if not yol.exists():
        return pd.DataFrame(columns=DUZELTME_SUTUNLARI)
    return pd.read_csv(yol, comment="#", dtype={"kod": str, "tarih": str, "aciklama": str, "kaynak": str})


def duzeltmeleri_dogrula(tablo: pd.DataFrame, veri: dict[str, pd.DataFrame]) -> list[str]:
    """Kaydetmeden önce kontrol: kod listede mi, tarih o hissenin işlem günü mü, oran pozitif mi, tekrar var mı."""
    hatalar = []
    for i, s in tablo.reset_index(drop=True).iterrows():
        satir = f"Satır {i + 1}"
        kod = str(s.get("kod") or "").strip().upper()
        df = veri.get(config.yf_sembol(kod)) if kod else None
        if df is None:
            hatalar.append(f"{satir}: '{kod}' hisse listesinde yok.")
            continue
        try:
            tarih = pd.Timestamp(str(s.get("tarih")))
        except (ValueError, TypeError):
            hatalar.append(f"{satir}: tarih okunamadı (YYYY-AA-GG olmalı).")
            continue
        if tarih not in df.index:
            hatalar.append(f"{satir}: {kod} için {tarih.date()} bir işlem günü değil.")
        try:
            oran = float(s.get("oran"))
            if not oran > 0:
                raise ValueError
        except (ValueError, TypeError):
            hatalar.append(f"{satir}: oran pozitif bir sayı olmalı (ör. %900 bedelsiz = 10).")
    anahtar = tablo["kod"].astype(str).str.upper() + "|" + tablo["tarih"].astype(str)
    for tekrar in anahtar[anahtar.duplicated()].unique():
        hatalar.append(f"Aynı hisse ve tarih iki kez girilmiş: {tekrar.replace('|', ' ')}")
    return hatalar


def duzeltmeleri_kaydet(tablo: pd.DataFrame, yol: Path = DUZELTME_DOSYASI) -> None:
    """Dosyanın baştaki açıklama satırlarını koruyarak tabloyu yazar."""
    aciklama = []
    if yol.exists():
        aciklama = [s for s in yol.read_text(encoding="utf-8").splitlines() if s.startswith("#")]
    tablo = tablo[DUZELTME_SUTUNLARI].copy()
    tablo["kod"] = tablo["kod"].astype(str).str.strip().str.upper()
    tablo["tarih"] = pd.to_datetime(tablo["tarih"]).dt.strftime("%Y-%m-%d")
    govde = tablo.sort_values(["kod", "tarih"]).to_csv(index=False, lineterminator="\n")
    yol.write_text("\n".join(aciklama) + ("\n" if aciklama else "") + govde, encoding="utf-8")


# ---------------------------------------------------------------------------
# Hisse evreni (referans/bist100.csv)
# ---------------------------------------------------------------------------

def evren_dogrula(kodlar: list[str]) -> list[str]:
    hatalar = []
    temiz = [k.strip().upper() for k in kodlar if k and k.strip()]
    for k in temiz:
        if not k.isalnum() or not 3 <= len(k) <= 6:
            hatalar.append(f"'{k}' geçerli bir BIST kodu gibi görünmüyor (3-6 harf/rakam).")
    if len(set(temiz)) != len(temiz):
        hatalar.append("Listede tekrar eden kod var.")
    if len(temiz) < 10:
        hatalar.append("Liste en az 10 hisse içermeli.")
    return hatalar


def evren_kaydet(kodlar: list[str], yol: Path = EVREN_DOSYASI) -> None:
    temiz = sorted({k.strip().upper() for k in kodlar if k and k.strip()})
    pd.DataFrame({"kod": temiz}).to_csv(yol, index=False, lineterminator="\n")


# ---------------------------------------------------------------------------
# Git kaydı ve arka plan komutları
# ---------------------------------------------------------------------------

def git_kaydet(yollar: list[Path], mesaj: str) -> tuple[bool, str]:
    """Sadece verilen dosyaları commit'ler (elle yapılan veri değişikliklerinin kaydı)."""
    goreli = [str(Path(y).relative_to(config.KOK_DIZIN)) for y in yollar]
    try:
        subprocess.run(["git", "add", "--", *goreli], cwd=config.KOK_DIZIN, check=True, capture_output=True)
        s = subprocess.run(["git", "commit", "-m", mesaj, "--", *goreli], cwd=config.KOK_DIZIN,
                           capture_output=True, text=True, encoding="utf-8")
        return s.returncode == 0, (s.stdout + s.stderr).strip()
    except (OSError, subprocess.CalledProcessError) as hata:
        return False, str(hata)


KOMUTLAR = {
    "Fiyat ve makro veriyi güncelle": [sys.executable, "-m", "src.data.guncelle"],
    "İleri test kayıtlarını doğrula": [sys.executable, "-m", "src.ileri_test.gunluk", "--dogrula"],
    "İleri test Excel'ini yeniden üret": [sys.executable, "-m", "src.ileri_test.gunluk", "--excel"],
    "Backtest raporunu yeniden üret": [sys.executable, "-m", "src.backtest.rapor"],
}


def komut_calistir(ad: str, zaman_asimi: int = 1800) -> tuple[int, str]:
    """Tanımlı bir komutu alt süreçte çalıştırır (sadece KOMUTLAR listesindekiler)."""
    ortam = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    s = subprocess.run(KOMUTLAR[ad], cwd=config.KOK_DIZIN, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=zaman_asimi, env=ortam)
    cikti = "\n".join(satir for satir in (s.stdout + s.stderr).splitlines() if "possibly delisted" not in satir)
    return s.returncode, cikti[-6000:]


def log_sonu(yol: Path, satir: int = 15) -> str:
    if not yol.exists():
        return ""
    return "\n".join(yol.read_text(encoding="utf-8", errors="replace").splitlines()[-satir:])
