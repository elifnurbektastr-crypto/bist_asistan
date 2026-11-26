"""Grafik aracının Python tarafı: mum verisi, zaman aralığı, indikatörler ve Plotly şekil tanımı.

Fiyat: SADECE bölünmeye göre düzeltilmiş (temettüye göre değil). Böylece son fiyat aracı
kurumdaki fiyatla aynıdır ve bedelsiz bölünmeler grafikte sahte uçurum oluşturmaz.
Şekil tanımı JSON olarak tarayıcıdaki bileşene gönderilir; çizim araçları orada çalışır.
"""

import json

import numpy as np
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go

from src.features.indicators import rsi

RENKLER = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6"]   # en fazla 6 çizgi
YUKSELIS, DUSUS = "#1baf7a", "#e34948"
METIN, IKINCIL, IZGARA, ZEMIN = "#0b0b0b", "#52514e", "#ebeae6", "#fcfcfb"
ARALIKLAR = {"Günlük": None, "Haftalık": "W-FRI", "Aylık": "ME"}
GUN_ICI_ARALIKLAR = {"5 dakika": None, "15 dakika": "15min", "1 saat": "60min"}
MAKS_CIZGI = 6


def bolunme_duzeltilmis(df: pd.DataFrame) -> pd.DataFrame:
    """Ham OHLCV'yi sadece bölünmelere göre düzeltir (bugünkü hisse bazına getirir).

    t gününün fiyatı, t'den SONRAKİ bölünme oranlarının çarpımına bölünür; hacim çarpılır.
    """
    oran = df["bolunme"].where(df["bolunme"] > 0, 1.0)
    sonraki = oran[::-1].cumprod()[::-1].shift(-1, fill_value=1.0)
    sonuc = pd.DataFrame({
        "acilis": df["acilis"] / sonraki, "yuksek": df["yuksek"] / sonraki,
        "dusuk": df["dusuk"] / sonraki, "kapanis": df["kapanis"] / sonraki,
        "hacim": df["hacim"] * sonraki,
    }, index=df.index)
    return sonuc


def yeniden_ornekle(ohlc: pd.DataFrame, aralik: str) -> pd.DataFrame:
    """Günlük mumları haftalık/aylık mumlara çevirir (ilk açılış, en yüksek, en düşük, son kapanış)."""
    kural = ARALIKLAR[aralik]
    if kural is None:
        return ohlc
    sonuc = ohlc.resample(kural).agg({"acilis": "first", "yuksek": "max", "dusuk": "min",
                                      "kapanis": "last", "hacim": "sum"}).dropna(subset=["kapanis"])
    # Mumun tarihi, o dönemin son işlem günü olsun (henüz bitmemiş hafta/ay için bugün)
    son_gunler = ohlc["kapanis"].groupby(pd.Grouper(freq=kural)).apply(lambda s: s.index.max()).dropna()
    sonuc.index = pd.DatetimeIndex(son_gunler.reindex(sonuc.index).values)
    return sonuc


def gun_ici_ohlc(mumlar: pd.DataFrame, aralik: str) -> pd.DataFrame:
    """Bir hissenin 5 dakikalık mumlarını (zaman sütunlu) seçilen gün içi aralığa çevirir.

    Her gün kendi içinde gruplanır; bir günün son mumu ertesi güne taşmaz.
    """
    ohlc = mumlar.set_index("zaman")[["acilis", "yuksek", "dusuk", "kapanis", "hacim"]].sort_index()
    kural = GUN_ICI_ARALIKLAR[aralik]
    if kural is None:
        return ohlc
    return (ohlc.resample(kural, origin="start_day")
                .agg({"acilis": "first", "yuksek": "max", "dusuk": "min", "kapanis": "last", "hacim": "sum"})
                .dropna(subset=["kapanis"]))


def macd(kapanis: pd.Series, hizli: int = 12, yavas: int = 26, sinyal: int = 9) -> pd.DataFrame:
    """MACD çizgisi, sinyal çizgisi ve histogram."""
    cizgi = kapanis.ewm(span=hizli, adjust=False).mean() - kapanis.ewm(span=yavas, adjust=False).mean()
    sinyal_cizgisi = cizgi.ewm(span=sinyal, adjust=False).mean()
    return pd.DataFrame({"macd": cizgi, "sinyal": sinyal_cizgisi, "histogram": cizgi - sinyal_cizgisi})


def bollinger(kapanis: pd.Series, pencere: int = 20, k: float = 2.0) -> pd.DataFrame:
    """Orta bant (hareketli ortalama) ± k standart sapma."""
    orta = kapanis.rolling(pencere).mean()
    sapma = kapanis.rolling(pencere).std()
    return pd.DataFrame({"orta": orta, "ust": orta + k * sapma, "alt": orta - k * sapma})


def periyotlari_oku(metin: str) -> list[int]:
    """'20, 50 200' gibi bir metinden geçerli periyotları okur (2-400 arası, tekrarsız)."""
    sayilar = []
    for parca in metin.replace(",", " ").split():
        if parca.isdigit() and 2 <= int(parca) <= 400 and int(parca) not in sayilar:
            sayilar.append(int(parca))
    return sayilar


def eksik_gunler(index: pd.DatetimeIndex) -> list[str]:
    """Hafta içi olup işlem olmayan günler (tatiller): grafikte boşluk bırakmamak için atlanır."""
    tum = pd.bdate_range(index.min(), index.max())
    return [d.strftime("%Y-%m-%d") for d in tum.difference(index)]


def sekil_olustur(df: pd.DataFrame, kod: str, aralik: str = "Günlük", donem_gun: int | None = 252,
                  ma: list[int] = (), ema: list[int] = (), bollinger_acik: bool = False,
                  rsi_acik: bool = False, macd_acik: bool = False, gun_ici: pd.DataFrame | None = None,
                  mobil: bool = False) -> dict:
    """Mum grafiği + indikatörler. Plotly JSON tanımı döner (bileşene gönderilir).

    İndikatörler tüm geçmiş üzerinde hesaplanır, sonra dönem kesilir: böylece MA200 gibi uzun
    ortalamalar dönemin ilk gününden itibaren doğru değer gösterir.
    """
    # gun_ici verilirse (5 dk / 15 dk / 1 saat) df yerine o mumlar çizilir
    ohlc = gun_ici if gun_ici is not None else yeniden_ornekle(bolunme_duzeltilmis(df), aralik)
    k = ohlc["kapanis"]
    ust_cizgiler = {}
    for n in ma:
        ust_cizgiler[f"MA {n}"] = k.rolling(n).mean()
    for n in ema:
        ust_cizgiler[f"EMA {n}"] = k.ewm(span=n, adjust=False).mean()
    ust_cizgiler = dict(list(ust_cizgiler.items())[:MAKS_CIZGI])
    bb = bollinger(k) if bollinger_acik else None
    r = rsi(k) if rsi_acik else None
    m = macd(k) if macd_acik else None

    if donem_gun and gun_ici is None:
        bas = ohlc.index[-min(len(ohlc), max(1, int(donem_gun / {"Günlük": 1, "Haftalık": 5, "Aylık": 21}[aralik])))]
        kes = lambda s: s.loc[bas:]   # noqa: E731
    else:
        kes = lambda s: s   # noqa: E731
    ohlc = kes(ohlc)

    paneller = ["fiyat", "hacim"] + (["rsi"] if rsi_acik else []) + (["macd"] if macd_acik else [])
    yukseklikler = {"fiyat": 0.62, "hacim": 0.13, "rsi": 0.17, "macd": 0.17}
    oranlar = [yukseklikler[p] for p in paneller]
    fig = make_subplots(rows=len(paneller), cols=1, shared_xaxes=True, vertical_spacing=0.025,
                        row_heights=[o / sum(oranlar) for o in oranlar])
    x = ohlc.index.strftime("%Y-%m-%d %H:%M" if gun_ici is not None else "%Y-%m-%d")

    fig.add_trace(go.Candlestick(
        x=x, open=ohlc["acilis"], high=ohlc["yuksek"], low=ohlc["dusuk"], close=ohlc["kapanis"], name=kod,
        increasing=dict(line=dict(color=YUKSELIS, width=1), fillcolor=YUKSELIS),
        decreasing=dict(line=dict(color=DUSUS, width=1), fillcolor=DUSUS), showlegend=False), row=1, col=1)
    if bb is not None:
        b = kes(bb)
        fig.add_trace(go.Scatter(x=x, y=b["ust"], line=dict(color="#a3a29d", width=1), name="Bollinger üst",
                                 hoverinfo="skip", showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=x, y=b["alt"], line=dict(color="#a3a29d", width=1), fill="tonexty",
                                 fillcolor="rgba(163,162,157,0.12)", name="Bollinger (20, 2)"), row=1, col=1)
    for i, (ad, seri) in enumerate(ust_cizgiler.items()):
        fig.add_trace(go.Scatter(x=x, y=kes(seri), name=ad, mode="lines",
                                 line=dict(color=RENKLER[i], width=1.6)), row=1, col=1)

    renk = np.where(ohlc["kapanis"] >= ohlc["acilis"], YUKSELIS, DUSUS)
    fig.add_trace(go.Bar(x=x, y=ohlc["hacim"], marker_color=renk, marker_line_width=0, opacity=0.6,
                         name="Hacim", showlegend=False, hovertemplate="%{y:,.0f}"), row=2, col=1)
    satir = 3
    paneller_etiket = [(2, "Hacim")]
    if r is not None:
        fig.add_trace(go.Scatter(x=x, y=kes(r), name="RSI 14", line=dict(color=RENKLER[5], width=1.5),
                                 showlegend=False), row=satir, col=1)
        for seviye in (30, 70):
            fig.add_hline(y=seviye, line=dict(color="#a3a29d", width=1, dash="dot"), row=satir, col=1)
        fig.update_yaxes(range=[0, 100], tickvals=[30, 50, 70], row=satir, col=1)
        paneller_etiket.append((satir, "RSI (14)"))
        satir += 1
    if m is not None:
        mm = kes(m)
        fig.add_trace(go.Bar(x=x, y=mm["histogram"], marker_color=np.where(mm["histogram"] >= 0, YUKSELIS, DUSUS),
                             opacity=0.5, name="MACD histogram", showlegend=False), row=satir, col=1)
        fig.add_trace(go.Scatter(x=x, y=mm["macd"], name="MACD", line=dict(color=RENKLER[0], width=1.4),
                                 showlegend=False), row=satir, col=1)
        fig.add_trace(go.Scatter(x=x, y=mm["sinyal"], name="Sinyal", line=dict(color=RENKLER[1], width=1.4),
                                 showlegend=False), row=satir, col=1)
        paneller_etiket.append((satir, "MACD (12, 26, 9)"))

    araliklar = [dict(bounds=["sat", "mon"])]
    if gun_ici is not None:
        araliklar.append(dict(bounds=[18.25, 10], pattern="hour"))   # seans dışı saatler (gece) boşluk olmasın
    elif aralik == "Günlük":
        araliklar.append(dict(values=eksik_gunler(ohlc.index)))
    fig.update_xaxes(rangebreaks=araliklar if (aralik == "Günlük" or gun_ici is not None) else [],
                     showgrid=False, rangeslider_visible=False, linecolor="#c9c8c3",
                     hoverformat="%d.%m.%Y %H:%M" if gun_ici is not None else "%d.%m.%Y")
    fig.update_yaxes(gridcolor=IZGARA, zeroline=False, side="right", ticks="outside", ticklen=4,
                     tickcolor="rgba(0,0,0,0)", automargin=True)
    fig.update_yaxes(showticklabels=False, row=2, col=1)
    for no, etiket in paneller_etiket:
        eksen = "y" if no == 1 else f"y{no}"
        fig.add_annotation(text=etiket, xref="paper", x=0.002, yref=f"{eksen} domain", y=0.98, showarrow=False,
                           xanchor="left", yanchor="top", font=dict(size=11, color=IKINCIL))
    fig.update_layout(
        height=(360 + 100 * (len(paneller) - 2)) if mobil else (480 + 130 * (len(paneller) - 2)),
        margin=dict(l=4, r=46, t=26, b=30) if mobil else dict(l=10, r=70, t=30, b=40),
        paper_bgcolor=ZEMIN, plot_bgcolor=ZEMIN, font=dict(color=IKINCIL, size=11 if mobil else 12),
        hovermode="x unified", dragmode="pan", showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, traceorder="normal"),
        newshape=dict(line=dict(color="#6250d6", width=2), fillcolor="rgba(98,80,214,0.12)"),
        hoverlabel=dict(bgcolor="white", font_color=METIN),
    )
    return json.loads(fig.to_json())   # numpy dizileri JSON'a çevrilir (bileşene gönderilebilir)


def son_degerler(df: pd.DataFrame) -> dict:
    """Kullanıcının yorumlayabileceği son indikatör değerleri (günlük)."""
    k = bolunme_duzeltilmis(df)["kapanis"]
    m, b = macd(k), bollinger(k)
    return {
        "kapanis": float(k.iloc[-1]), "rsi_14": float(rsi(k).iloc[-1]),
        "ma_20": float(k.rolling(20).mean().iloc[-1]), "ma_50": float(k.rolling(50).mean().iloc[-1]),
        "ma_200": float(k.rolling(200).mean().iloc[-1]) if len(k) >= 200 else None,
        "macd": float(m["macd"].iloc[-1]), "macd_sinyal": float(m["sinyal"].iloc[-1]),
        "bollinger_ust": float(b["ust"].iloc[-1]), "bollinger_alt": float(b["alt"].iloc[-1]),
    }
