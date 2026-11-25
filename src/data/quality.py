"""Veri kalitesi kontrolleri: eksik gün, sıfır hacim, limit aşımı, bölünme varsayımı."""

import pandas as pd

from src import config


SUPHELI_SICRAMA_ESIGI = 0.35   # hiçbir fiyat limiti rejimiyle açıklanamayacak günlük hareket


def supheli_sicramalar(df: pd.DataFrame, esik: float = SUPHELI_SICRAMA_ESIGI) -> pd.DataFrame:
    """Düzeltilmiş seride |getiri| > esik olan günler: büyük ihtimalle Yahoo'nun
    kaydetmediği bir bedelsiz/bedelli sermaye artırımı.

    'tahmini_oran' = önceki kapanış / o günkü kapanış. Bu yalnızca ipucudur;
    gerçek oran KAP duyurusundan doğrulanıp referans/duzeltmeler.csv'ye yazılmalıdır.
    """
    getiri = df["duz_kapanis"].pct_change()
    secili = getiri.abs() > esik
    onceki = df["kapanis"].shift(1)
    return pd.DataFrame({
        "getiri": getiri[secili],
        "onceki_kapanis": onceki[secili],
        "kapanis": df.loc[secili, "kapanis"],
        "tahmini_oran": (onceki / df["kapanis"])[secili],
    })


def kalite_raporu(df: pd.DataFrame, takvim: pd.DatetimeIndex | None = None) -> dict:
    """Tek bir sembolün standart fiyat tablosu için kalite özetini döner.

    takvim: referans işlem günleri (genelde XU100 tarihleri). Verilirse eksik günler sayılır.
    """
    getiri = df["duz_kapanis"].pct_change()
    # Bugünkü günlük limit ±%10; eski dönemlerde limitler farklıydı, bu yüzden
    # limit aşımı tek başına hata değildir. Asıl hata işareti 'supheli_sicrama'dır.
    limit_asimi = getiri[getiri.abs() > config.GUNLUK_FIYAT_LIMITI + 0.005]
    ohlc_tutarsiz = (
        (df["yuksek"] < df["dusuk"])
        | (df["kapanis"] > df["yuksek"] * 1.001)
        | (df["kapanis"] < df["dusuk"] * 0.999)
    )
    rapor = {
        "satir": len(df),
        "ilk_tarih": df.index.min().date() if len(df) else None,
        "son_tarih": df.index.max().date() if len(df) else None,
        "nan": int(df[["kapanis", "duz_kapanis"]].isna().sum().sum()),
        "yinelenen_tarih": int(df.index.duplicated().sum()),
        "sifir_hacim": int((df["hacim"] == 0).sum()),
        "ohlc_tutarsiz": int(ohlc_tutarsiz.sum()),
        "limit_asimi": len(limit_asimi),
        "limit_asimi_tarihleri": [d.date() for d in limit_asimi.index],
        "supheli_sicrama": len(supheli_sicramalar(df)),
        "bolunme": int((df["bolunme"] > 0).sum()),
        "temettu": int((df["temettu"] > 0).sum()),
    }
    if takvim is not None and len(df):
        aralik = takvim[(takvim >= df.index.min()) & (takvim <= df.index.max())]
        rapor["eksik_gun"] = len(aralik.difference(df.index))
        rapor["fazla_gun"] = len(df.index.difference(takvim))
    return rapor


def kalite_tablosu(veri: dict[str, pd.DataFrame], takvim: pd.DatetimeIndex | None = None) -> pd.DataFrame:
    """Tüm semboller için kalite raporlarını tek tabloda toplar."""
    satirlar = {s: kalite_raporu(df, takvim) for s, df in veri.items()}
    return pd.DataFrame.from_dict(satirlar, orient="index")


def bolunme_kontrolu(df: pd.DataFrame) -> pd.DataFrame:
    """'yfinance Close bölünmeye göre düzeltilmiştir' varsayımını her bölünme gününde sınar.

    Ham kapanış bölünme gününde oran kadar düşmeli, düzeltilmiş kapanış düşmemeli.
    Yani (ham sıçrama / düzeltilmiş sıçrama) ≈ bölünme oranı olmalı.
    'sapma' ≈ 1 ise varsayım doğru; ≈ oran ise yanlış (ham fiyat iki kez çarpılmış).
    """
    satirlar = []
    for tarih in df.index[df["bolunme"] > 0]:
        konum = df.index.get_loc(tarih)
        if konum == 0:
            continue
        onceki = df.iloc[konum - 1]
        bugun = df.iloc[konum]
        ham_sicrama = onceki["kapanis"] / bugun["kapanis"]
        duz_sicrama = onceki["duz_kapanis"] / bugun["duz_kapanis"]
        oran = bugun["bolunme"]
        satirlar.append({
            "tarih": tarih.date(),
            "oran": oran,
            "ham_sicrama": round(ham_sicrama, 4),
            "duz_sicrama": round(duz_sicrama, 4),
            "sapma": round(ham_sicrama / duz_sicrama / oran, 4),
        })
    return pd.DataFrame(satirlar)
