"""Gün içi (canlı) veri: 5 dakikalık mumlar ve anlık fiyat tablosu.

BIST'in gerçek zamanlı verisi lisanslıdır; ücretsiz kaynaklar (Yahoo dahil) 15 dakika gecikmelidir.
Akış:
  * GitHub'daki görev seans boyunca 15 dakikada bir: Yahoo → data/anlik/*.parquet → Supabase
  * Uygulama: önce Yahoo'yu doğrudan dener (kısa zaman aşımıyla), olmazsa Supabase'deki son kopyayı okur.
Model ve ileri test bu veriyi KULLANMAZ: seans içi fiyat kesinleşmemiştir (look-ahead riski).

Kullanım: python -m src.data.anlik --kaydet      (Yahoo'dan çek, kaydet, buluta yükle)
"""

import argparse
import logging

import pandas as pd

from src import config
from src.data import cache

log = logging.getLogger(__name__)
KLASOR = "anlik"
ARALIK = "5m"
GECMIS = "5d"          # son 5 işlem gününün 5 dakikalık mumları (gün içi grafik için)
GECIKME_DK = 15


def _uzun_tablo(ham: pd.DataFrame, semboller: list[str]) -> pd.DataFrame:
    """yf.download çok sembollü çıktısını (zaman, kod) satırlı uzun tabloya çevirir."""
    parcalar = []
    for s in semboller:
        if isinstance(ham.columns, pd.MultiIndex):
            if s not in ham.columns.get_level_values(0):
                continue
            t = ham[s]
        else:
            t = ham
        t = t.dropna(subset=["Close"])
        if t.empty:
            continue
        idx = pd.DatetimeIndex(t.index)
        idx = idx.tz_convert(config.SAAT_DILIMI).tz_localize(None) if idx.tz is not None else idx
        parcalar.append(pd.DataFrame({
            "zaman": idx, "kod": s.replace(".IS", ""),
            "acilis": t["Open"].values, "yuksek": t["High"].values, "dusuk": t["Low"].values,
            "kapanis": t["Close"].values, "hacim": t["Volume"].values,
        }))
    if not parcalar:
        return pd.DataFrame(columns=["zaman", "kod", "acilis", "yuksek", "dusuk", "kapanis", "hacim"])
    return pd.concat(parcalar, ignore_index=True).sort_values(["kod", "zaman"]).reset_index(drop=True)


CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sembol}"
TARAYICI = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
ES_ZAMANLI = 8         # aynı anda en fazla bu kadar istek


def _grafik_cevabi_tablo(cevap: dict, sembol: str) -> pd.DataFrame:
    """Yahoo chart API cevabını (zaman, kod, OHLCV) tablosuna çevirir; boş mumları atar."""
    sonuc = (cevap.get("chart") or {}).get("result") or []
    if not sonuc or not sonuc[0].get("timestamp"):
        return _uzun_tablo(pd.DataFrame(), [])
    r = sonuc[0]
    q = r["indicators"]["quote"][0]
    zaman = (pd.to_datetime(r["timestamp"], unit="s", utc=True)
             .tz_convert(config.SAAT_DILIMI).tz_localize(None))
    df = pd.DataFrame({"zaman": zaman, "kod": sembol.replace(".IS", ""),
                       "acilis": q.get("open"), "yuksek": q.get("high"), "dusuk": q.get("low"),
                       "kapanis": q.get("close"), "hacim": q.get("volume")})
    return df.dropna(subset=["kapanis"]).reset_index(drop=True)


def _tek_sembol(oturum, sembol: str, aralik: str, gecmis: str, zaman_asimi: float) -> pd.DataFrame:
    try:
        r = oturum.get(CHART_URL.format(sembol=sembol), params={"interval": aralik, "range": gecmis},
                       headers=TARAYICI, timeout=zaman_asimi)
        r.raise_for_status()
        return _grafik_cevabi_tablo(r.json(), sembol)
    except Exception as hata:
        log.warning("%s gün içi veri alınamadı: %s", sembol, hata)
        return _uzun_tablo(pd.DataFrame(), [])


def yahoodan_cek(semboller: list[str], zaman_asimi: float = 10, aralik: str = ARALIK,
                 gecmis: str = GECMIS) -> pd.DataFrame:
    """Sembollerin gün içi mumlarını Yahoo'nun chart adresinden çeker (boşsa boş tablo).

    yfinance yerine doğrudan chart adresi kullanılır: yfinance'in oturum (crumb) adımı sık sık
    engellenip dakikalarca takılıyor; chart adresi oturum istemez ve 15 dk gecikmeli veriyi anında verir.
    Varsayılan: son 5 günün 5 dakikalık mumları (toplu görev). Uygulama seçili hisse için 1 dakikalık ister.
    """
    from concurrent.futures import ThreadPoolExecutor

    import requests
    with requests.Session() as oturum, ThreadPoolExecutor(ES_ZAMANLI) as havuz:
        parcalar = list(havuz.map(lambda s: _tek_sembol(oturum, s, aralik, gecmis, zaman_asimi), semboller))
    parcalar = [x for x in parcalar if len(x)]
    if not parcalar:
        return _uzun_tablo(pd.DataFrame(), [])
    return pd.concat(parcalar, ignore_index=True).sort_values(["kod", "zaman"]).reset_index(drop=True)


def anlik_tablo(mumlar: pd.DataFrame) -> pd.DataFrame:
    """Her hisse için: son fiyat, önceki günün kapanışına göre değişim, gün içi açılış/yüksek/düşük/hacim.

    Önceki kapanış = son işlem gününden bir önceki günün son 5 dakikalık mumunun kapanışı.
    """
    if mumlar.empty:
        return pd.DataFrame()
    m = mumlar.assign(gun=mumlar["zaman"].dt.normalize())
    satirlar = {}
    for kod, g in m.groupby("kod"):
        gunler = sorted(g["gun"].unique())
        bugun = g[g["gun"] == gunler[-1]]
        onceki = g[g["gun"] == gunler[-2]]["kapanis"].iloc[-1] if len(gunler) > 1 else float("nan")
        son = bugun["kapanis"].iloc[-1]
        satirlar[kod] = {
            "son_fiyat": son, "zaman": bugun["zaman"].iloc[-1], "gun": gunler[-1],
            "onceki_kapanis": onceki, "degisim": son / onceki - 1 if onceki == onceki else float("nan"),
            "gun_acilis": bugun["acilis"].iloc[0], "gun_yuksek": bugun["yuksek"].max(),
            "gun_dusuk": bugun["dusuk"].min(), "gun_hacim": bugun["hacim"].sum(),
        }
    return pd.DataFrame.from_dict(satirlar, orient="index").rename_axis("kod")


def bugunku_mum(mumlar: pd.DataFrame, kod: str) -> pd.Series | None:
    """Bir hissenin son işlem günündeki 5 dakikalık mumlarından günlük mum (seans içinde oluşmakta)."""
    g = mumlar[mumlar["kod"] == kod]
    if g.empty:
        return None
    gun = g["zaman"].dt.normalize().max()
    b = g[g["zaman"].dt.normalize() == gun]
    return pd.Series({"acilis": b["acilis"].iloc[0], "yuksek": b["yuksek"].max(), "dusuk": b["dusuk"].min(),
                      "kapanis": b["kapanis"].iloc[-1], "hacim": b["hacim"].sum()}, name=gun)


def kaydet(mumlar: pd.DataFrame) -> None:
    """Gün içi mumları ve anlık tabloyu yerel önbelleğe yazar."""
    cache.yaz(mumlar, "mumlar_5m", KLASOR)
    cache.yaz(anlik_tablo(mumlar).reset_index(), "anlik", KLASOR)


def oku() -> pd.DataFrame | None:
    """Önbellekteki gün içi mumlar (yoksa None)."""
    return cache.oku("mumlar_5m", KLASOR)


def main() -> None:
    ayr = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ayr.add_argument("--kaydet", action="store_true", help="Yahoo'dan çek, kaydet ve buluta yükle")
    ayr.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    semboller = [config.yf_sembol(h) for h in config.hisse_evreni()] + [config.ENDEKS, config.USDTRY]
    mumlar = yahoodan_cek(semboller)
    gelen = mumlar["kod"].nunique() if len(mumlar) else 0
    log.info("Gün içi veri: %d/%d sembol, son mum %s", gelen, len(semboller),
             mumlar["zaman"].max() if len(mumlar) else "-")
    if gelen < 0.5 * len(semboller):
        log.error("Yeterli gün içi veri gelmedi; kaydedilmedi.")
        raise SystemExit(1)
    kaydet(mumlar)
    from src import bulut
    if bulut.ayarlar()["secret"]:
        bulut.yukle(klasorler=[KLASOR])


if __name__ == "__main__":
    main()
