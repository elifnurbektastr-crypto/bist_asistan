"""Vektörel backtest motoru (hazır kütüphane yok, her satır açıklanabilir).

Zamanlama kuralı:
  - Strateji t günü KAPANIŞINDA sinyal üretir (sadece t'ye kadarki bilgiyle).
  - Pozisyon t+1 AÇILIŞINDA alınır ve bir sonraki açılışa kadar tutulur.
  - Bu yüzden getiriler açılıştan açılışa hesaplanır: r[t] = açılış[t+1] / açılış[t] - 1
Maliyet: pozisyon her değiştiğinde |değişim| × (komisyon + kayma).
Nakit: piyasa dışındaki para istenirse politika faizi kazanır (para piyasası fonu varsayımı).
"""

import numpy as np
import pandas as pd

from src import config
from src.features.indicators import HEDEF_UFKU

YILLIK_GUN = 252


def acilis_getirisi(df: pd.DataFrame) -> pd.Series:
    """t açılışından t+1 açılışına düzeltilmiş getiri (son gün bilinmez: NaN)."""
    a = df["duz_acilis"]
    return a.shift(-1) / a - 1


def gunluk_faiz(nakit_faizi: pd.Series | None, takvim: pd.DatetimeIndex) -> pd.Series:
    """Yıllık faiz serisini (oran, ör. 0.36) işlem günü başına getiriye çevirir."""
    if nakit_faizi is None:
        return pd.Series(0.0, index=takvim)
    faiz = nakit_faizi.reindex(takvim.union(nakit_faizi.index)).ffill().reindex(takvim).fillna(0)
    return faiz / YILLIK_GUN


def backtest(df: pd.DataFrame, hedef_pozisyon: pd.Series, maliyet: float = config.ISLEM_MALIYETI,
             nakit_faizi: pd.Series | None = None, baslangic=None, bitis=None) -> pd.DataFrame:
    """Tek varlık backtest'i. Dönen tablo günlük: pozisyon, getiriler, maliyet, sermaye.

    hedef_pozisyon: t kapanışında istenen pozisyon (0-1). Tüm geçmiş üzerinde hesaplanıp
    verilmelidir (göstergelerin ısınma dönemi için); sonra [baslangic, bitis] aralığı kesilir.
    """
    pozisyon = hedef_pozisyon.reindex(df.index).shift(1).fillna(0.0)   # t-1 kararı t açılışında
    tablo = pd.DataFrame({"pozisyon": pozisyon, "varlik_getirisi": acilis_getirisi(df)})
    tablo = tablo.loc[baslangic:bitis].dropna(subset=["varlik_getirisi"])
    onceki = tablo["pozisyon"].shift(1, fill_value=0.0)                  # aralık başında elde nakit var
    tablo["maliyet"] = (tablo["pozisyon"] - onceki).abs() * maliyet
    tablo["nakit_getirisi"] = (1 - tablo["pozisyon"]) * gunluk_faiz(nakit_faizi, tablo.index)
    tablo["strateji_getirisi"] = (tablo["pozisyon"] * tablo["varlik_getirisi"]
                                  + tablo["nakit_getirisi"] - tablo["maliyet"])
    tablo["sermaye"] = (1 + tablo["strateji_getirisi"]).cumprod()
    return tablo


def getiri_matrisi(veri: dict[str, pd.DataFrame], takvim: pd.DatetimeIndex) -> pd.DataFrame:
    """Tarih × hisse açılıştan açılışa getiri tablosu (takvime hizalı)."""
    return pd.DataFrame({s.replace(".IS", ""): acilis_getirisi(df) for s, df in veri.items()}).reindex(takvim)


def portfoy_agirliklari(olasilik: pd.Series, esik: float, n: int,
                        vol: pd.Series | None = None) -> pd.Series:
    """Bir karar günü için ağırlıklar: eşiği aşan en yüksek olasılıklı n hisse.

    Her hisseye en fazla 1/n pay düşer; eşiği aşan hisse n'den azsa kalan pay nakitte bekler
    (model emin değilse yatırım da azalır). vol verilirse seçilenler arasında
    1/volatilite ile ağırlıklandırılır (oynak hisseye daha az para).
    """
    adaylar = olasilik[olasilik > esik].sort_values(ascending=False).head(n)
    if adaylar.empty:
        return pd.Series(dtype=float)
    if vol is None:
        return pd.Series(1.0 / n, index=adaylar.index)
    ters = 1 / vol.reindex(adaylar.index).clip(lower=0.05).fillna(vol.median())
    return ters / ters.sum() * len(adaylar) / n


def portfoy_backtest(getiriler: pd.DataFrame, olasiliklar: pd.DataFrame, esik: float = 0.60, n: int = 10,
                     ufuk: int = HEDEF_UFKU, maliyet: float = config.ISLEM_MALIYETI,
                     nakit_faizi: pd.Series | None = None, vol: pd.DataFrame | None = None) -> pd.DataFrame:
    """Her `ufuk` günde bir yeniden dengelenen portföy.

    getiriler: tarih × hisse açılıştan açılışa getiri (getiri_matrisi)
    olasiliklar: tarih × hisse model olasılığı (karar günü kapanışında bilinen)
    vol: tarih × hisse beklenen volatilite (isteğe bağlı, ters volatilite ağırlığı için)
    Basitleştirme: ağırlıklar dönem içinde fiyatla kaymaz, her dengelemede hedefe döner.
    """
    takvim = olasiliklar.index.intersection(getiriler.index)
    karar_gunleri = takvim[::ufuk]
    agirlik = pd.DataFrame(0.0, index=getiriler.index, columns=getiriler.columns)
    for i, gun in enumerate(karar_gunleri):
        w = portfoy_agirliklari(olasiliklar.loc[gun].dropna(), esik, n,
                                None if vol is None else vol.loc[gun].dropna())
        # Karar 'gun' kapanışında; uygulama bir sonraki işlem günü açılışından itibaren
        bas = getiriler.index.searchsorted(gun, side="right")
        son = (getiriler.index.searchsorted(karar_gunleri[i + 1], side="right")
               if i + 1 < len(karar_gunleri) else len(getiriler.index))
        agirlik.iloc[bas:son] = 0.0
        if len(w):
            agirlik.iloc[bas:son, agirlik.columns.get_indexer(w.index)] = w.values
    ilk = getiriler.index.searchsorted(karar_gunleri[0], side="right")
    agirlik, getiriler = agirlik.iloc[ilk:], getiriler.iloc[ilk:]
    getiriler = getiriler.dropna(how="all")
    agirlik = agirlik.reindex(getiriler.index)

    hisse_payi = agirlik.sum(axis=1)
    devir = agirlik.diff().abs().sum(axis=1)
    devir.iloc[0] = agirlik.iloc[0].abs().sum()
    tablo = pd.DataFrame({
        "hisse_getirisi": (agirlik * getiriler.fillna(0)).sum(axis=1),
        "nakit_getirisi": (1 - hisse_payi) * gunluk_faiz(nakit_faizi, getiriler.index),
        "maliyet": devir * maliyet,
        "hisse_payi": hisse_payi,
        "hisse_sayisi": (agirlik > 0).sum(axis=1),
    })
    tablo["strateji_getirisi"] = tablo["hisse_getirisi"] + tablo["nakit_getirisi"] - tablo["maliyet"]
    tablo["sermaye"] = (1 + tablo["strateji_getirisi"]).cumprod()
    return tablo
