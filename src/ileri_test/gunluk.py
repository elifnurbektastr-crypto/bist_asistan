"""İleri test günlük komutu: veriyi güncelle → tahmin et → kaydet → git'e commit → Excel.

Kullanım:
  python -m src.ileri_test.gunluk             # her akşam (Görev Zamanlayıcı çalıştırır)
  python -m src.ileri_test.gunluk --dondur    # ileri test başında bir kez: modeli dondur
  python -m src.ileri_test.gunluk --dogrula   # kayıtların değişmediğini kontrol et
  python -m src.ileri_test.gunluk --excel     # sadece Excel'i yeniden üret
  python -m src.ileri_test.gunluk --acilis    # sabah 10:30: açılış fiyatlarını kaydet

Aynı gün birden çok kez çalıştırılabilir: kayıt zaten varsa yeni tahmin üretmez.
Kaçırılan günler sonradan doldurulmaz (o tahmin artık 'geleceği bilmeden' yapılmış olmaz).
"""

import argparse
import logging
import subprocess
import sys

import pandas as pd

from src import config
from src.data import cache, fetch
from src.features.indicators import veri_seti_olustur
from src import bulut
from src.ileri_test import acilis, excel, kayit
from src.ileri_test import model as it_model
from src.models import deney

log = logging.getLogger("ileri_test")


def _gunluk_kayit_ayarla() -> None:
    """Hem ekrana hem data/ileri_test.log dosyasına yazar."""
    config.VERI_DIZINI.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(config.VERI_DIZINI / "ileri_test.log", encoding="utf-8")])


def _semboller() -> list[str]:
    return [config.yf_sembol(h) for h in config.hisse_evreni()] + [config.ENDEKS, config.USDTRY]


def _veriyi_ayir(veri: dict) -> tuple[dict, pd.DataFrame, pd.DataFrame | None]:
    veri = dict(veri)
    return veri, veri.pop(config.ENDEKS, None), veri.pop(config.USDTRY, None)


def git_commit(tarih: str, tur: str = "tahminleri") -> None:
    """Sadece ileri test kayıtlarını commit'ler (başka değişikliklere dokunmaz)."""
    yollar = [p for p in ["ileri_test/tahminler", "ileri_test/zincir.csv", "ileri_test/acilislar",
                          "ileri_test/acilis_zincir.csv", "ileri_test/model_surumu.json"]
              if (config.KOK_DIZIN / p).exists()]
    try:
        subprocess.run(["git", "add", "--", *yollar], cwd=config.KOK_DIZIN, check=True, capture_output=True)
        sonuc = subprocess.run(
            ["git", "commit", "-m", f"İleri test: {tarih} {tur}", "--", *yollar],
            cwd=config.KOK_DIZIN, capture_output=True, text=True, encoding="utf-8")
        if sonuc.returncode == 0:
            log.info("git commit yapıldı: %s", tarih)
        else:
            log.warning("git commit yapılamadı: %s", (sonuc.stdout + sonuc.stderr).strip()[:300])
    except (OSError, subprocess.CalledProcessError) as hata:
        log.warning("git çalıştırılamadı: %s", hata)


def yayinla() -> None:
    """Kayıtları GitHub'a gönderir, veri dosyalarını Supabase'e yükler. Hata görevi durdurmaz.

    GitHub'daki tarihli commit'ler ileri test kayıtlarının sonradan değiştirilmediğinin
    herkese açık kanıtıdır; Supabase'deki dosyalar buluttaki uygulamanın veri kaynağıdır.
    """
    try:
        s = subprocess.run(["git", "push", "origin", "HEAD"], cwd=config.KOK_DIZIN, capture_output=True,
                           text=True, encoding="utf-8", timeout=180)
        if s.returncode == 0:
            log.info("GitHub'a gönderildi.")
        else:
            log.warning("GitHub'a gönderilemedi: %s", (s.stdout + s.stderr).strip()[:300])
    except (OSError, subprocess.TimeoutExpired) as hata:
        log.warning("git push çalıştırılamadı: %s", hata)
    if not bulut.ayarlar()["secret"]:
        log.info("SUPABASE_SECRET_KEY yok; buluta yükleme atlandı.")
        return
    try:
        bulut.yukle()
    except Exception as hata:
        log.warning("Buluta yüklenemedi: %s", hata)


def excel_guncelle(veri: dict | None = None) -> None:
    """Kayıtlardan Excel raporunu üretir (internete gitmez, önbellek yeterli)."""
    if veri is None:
        veri, _, _, _ = deney.onbellekten_veri()
    try:
        _, bilgi = it_model.yukle()
    except (FileNotFoundError, it_model.ModelDegisti) as hata:
        log.warning("Model bilgisi okunamadı: %s", hata)
        bilgi = None
    yol = excel.excel_uret(kayit.tum_tahminler(), veri, kayit.zinciri_oku(), kayit.dogrula(), bilgi,
                           acilis_kayitlari=kayit.tum_tahminler(tur="acilis"))
    log.info("Excel güncellendi: %s", yol)


def dondur() -> None:
    """İleri test başında modeli bir kez eğitip dondurur."""
    tablo = deney.veri_seti()
    bilgi = it_model.dondur(tablo)
    log.info("Model donduruldu: %s (eğitim sonu %s, %d satır, %d hisseye özel model)",
             bilgi["surum"], bilgi["egitim_son_tarih"], bilgi["egitim_satir"], bilgi["hisseye_ozel_model"])
    git_commit(f"model {bilgi['surum']} donduruldu")


def gunluk() -> int:
    """Günlük akış. Dönüş: 0 başarılı/yapacak iş yok, 1 tekrar denenmeli."""
    model, bilgi = it_model.yukle()   # model değişmişse burada durur
    veri, endeks, kur = _veriyi_ayir(fetch.fiyat_verisi(_semboller()))
    if endeks is None or not veri:
        log.error("Endeks ya da hisse verisi alınamadı; daha sonra tekrar denenecek.")
        return 1

    tarih = endeks.index[-1]
    guncel = {s: df for s, df in veri.items() if df.index[-1] == tarih}
    eski = sorted(s.replace(".IS", "") for s in veri if s not in guncel)
    if len(guncel) < 0.9 * len(veri):
        log.error("%s için hisselerin sadece %d/%d tanesi güncel; tekrar denenecek. Eksik: %s",
                  tarih.date(), len(guncel), len(veri), eski[:15])
        return 1

    zincir = kayit.zinciri_oku()
    if len(zincir) and zincir["tarih"].iloc[-1] >= tarih.strftime("%Y-%m-%d"):
        log.info("%s tahmini zaten kayıtlı; yeni işlem günü yok.", tarih.date())
        excel_guncelle(veri)
        return 0
    if pd.Timestamp.now(tz=config.SAAT_DILIMI) > kayit.son_gecerli_zaman(tarih):
        log.warning("%s için tahmin süresi doldu (seans açıldı); bu gün KAÇIRILDI.", tarih.date())
        excel_guncelle(veri)
        return 0

    tablo = veri_seti_olustur(guncel, endeks, kur, cache.oku("evds", "makro"))
    gun = tablo.xs(tarih, level="tarih", drop_level=False)
    gun = gun[gun["getiri_60"].notna()].droplevel("tarih")
    gun.index = pd.MultiIndex.from_arrays([gun.index], names=["kod"])
    kapanis = pd.Series({s.replace(".IS", ""): df["kapanis"].iloc[-1] for s, df in guncel.items()})
    tahmin = it_model.tahmin_uret(model, bilgi, gun, kapanis)

    yol = kayit.tahmin_kaydet(tahmin, tarih, bilgi["surum"])
    log.info("%s: %d hisse tahmini kaydedildi (%s). Güçlü al: %s. Güncel olmayan: %s",
             tarih.date(), len(tahmin), yol.name,
             ", ".join(tahmin.loc[tahmin["sinyal"] == "güçlü al", "kod"]) or "yok", eski or "yok")
    git_commit(tarih.strftime("%Y-%m-%d"))
    excel_guncelle(veri)
    yayinla()
    return 0


def main() -> None:
    ayr = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    grup = ayr.add_mutually_exclusive_group()
    grup.add_argument("--dondur", action="store_true", help="modeli dondur (bir kez)")
    grup.add_argument("--dogrula", action="store_true", help="kayıt bütünlüğünü kontrol et")
    grup.add_argument("--excel", action="store_true", help="sadece Excel'i yeniden üret")
    grup.add_argument("--acilis", action="store_true", help="sabah: açılış fiyatlarını kaydet")
    arg = ayr.parse_args()
    _gunluk_kayit_ayarla()

    if arg.dondur:
        dondur()
    elif arg.dogrula:
        sorunlar = kayit.dogrula()
        print("✓ Kayıtlar sağlam." if not sorunlar else "✗ SORUNLAR:\n  " + "\n  ".join(sorunlar))
        sys.exit(1 if sorunlar else 0)
    elif arg.excel:
        excel_guncelle()
    elif arg.acilis:
        try:
            kod = acilis.acilis_kaydet()
            if kod == 0:
                git_commit(pd.Timestamp.now(tz=config.SAAT_DILIMI).strftime("%Y-%m-%d"), "açılış fiyatları")
                yayinla()
            sys.exit(kod)
        except Exception:
            log.exception("Açılış kaydı hata verdi.")
            sys.exit(1)
    else:
        try:
            sys.exit(gunluk())
        except Exception:
            log.exception("Günlük ileri test çalışması hata verdi.")
            sys.exit(1)


if __name__ == "__main__":
    main()
