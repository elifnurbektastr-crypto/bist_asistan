"""Sabah açılış kaydı: seans açıldıktan sonra 100 hissenin açılış fiyatını zaman damgasıyla kaydeder.

Akşamki günlük veride açılış zaten var; bu kayıt, açılış fiyatının o saatte gerçekten
görüldüğünün kanıtıdır ve tahminlerin işleme girdiği fiyatı gün içinde gösterir.
Kayıt sadece o gün, seans bitmeden yapılabilir (kayit.son_gecerli_zaman).
"""

import logging

import pandas as pd

from src import config
from src.data import fetch
from src.ileri_test import kayit

log = logging.getLogger("ileri_test")
EN_ERKEN = "10:00"   # seans 10:00'da açılır; Yahoo verisi ~15 dk gecikmeli


def bugunku_satirlar(ham: dict[str, pd.DataFrame], bugun: pd.Timestamp) -> pd.DataFrame:
    """yfinance ham verisinden bugünün (henüz tamamlanmamış) satırlarını çıkarır."""
    satirlar = []
    for sembol, tablo in ham.items():
        idx = pd.DatetimeIndex(tablo.index)
        if idx.tz is not None:
            idx = idx.tz_convert(config.SAAT_DILIMI).tz_localize(None)
        tablo = tablo.set_axis(idx.normalize())
        if bugun.normalize() in tablo.index:
            s = tablo.loc[bugun.normalize()]
            s = s.iloc[-1] if isinstance(s, pd.DataFrame) else s
            satirlar.append({"kod": sembol.replace(".IS", ""), "acilis": float(s["Open"]),
                             "anlik_fiyat": float(s["Close"])})
    return pd.DataFrame(satirlar)


def acilis_kaydet(simdi: pd.Timestamp | None = None) -> int:
    """Bugünün açılış fiyatlarını kaydeder. Dönüş: 0 tamam/yapacak iş yok, 1 tekrar denenmeli."""
    simdi = simdi or pd.Timestamp.now(tz=config.SAAT_DILIMI)
    bugun = simdi.tz_localize(None).normalize()
    if bugun.dayofweek >= 5:
        log.info("Hafta sonu; açılış kaydı yok.")
        return 0
    zincir = kayit.zinciri_oku(tur="acilis")
    if len(zincir) and zincir["tarih"].iloc[-1] >= bugun.strftime("%Y-%m-%d"):
        log.info("%s açılış kaydı zaten var.", bugun.date())
        return 0
    if simdi < pd.Timestamp(f"{bugun.date()} {EN_ERKEN}", tz=config.SAAT_DILIMI):
        log.info("Seans henüz açılmadı.")
        return 1

    semboller = [config.yf_sembol(h) for h in config.hisse_evreni()]
    baslangic = (bugun - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    tablo = bugunku_satirlar(fetch._indir(semboller, baslangic), bugun)
    if tablo.empty:
        log.warning("%s için hiçbir hissede bugünün verisi yok (tatil ya da Yahoo erişimi yok).", bugun.date())
        return 1
    if len(tablo) < 0.9 * len(semboller):
        log.warning("Açılış: sadece %d/%d hisse geldi; tekrar denenecek.", len(tablo), len(semboller))
        return 1

    tablo["kayit_saati"] = simdi.strftime("%H:%M:%S")
    yol = kayit.tahmin_kaydet(tablo.sort_values("kod"), bugun, "-", simdi=simdi, tur="acilis")
    log.info("%s: %d hissenin açılış fiyatı kaydedildi (%s).", bugun.date(), len(tablo), yol.name)
    return 0
