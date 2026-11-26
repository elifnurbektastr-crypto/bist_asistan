"""Gün içi veri: tablo dönüşümü, anlık fiyat ve değişim, oluşan günlük mum, buluta alt küme yükleme."""

import json

import numpy as np
import pandas as pd
import pytest

from src import bulut
from src.data import anlik


def sahte_mumlar():
    """2 gün × 3 mum, 2 hisse (uzun tablo)."""
    satirlar = []
    for kod, taban in [("AAA", 100.0), ("BBB", 50.0)]:
        for gun, kayma in [("2026-11-25", 0.0), ("2026-11-26", 10.0)]:
            for i, saat in enumerate(["10:00", "10:05", "10:10"]):
                f = taban + kayma + i
                satirlar.append({"zaman": pd.Timestamp(f"{gun} {saat}"), "kod": kod, "acilis": f - 0.5,
                                 "yuksek": f + 1, "dusuk": f - 1, "kapanis": f, "hacim": 100.0})
    return pd.DataFrame(satirlar)


def test_uzun_tablo_yfinance_bicimi():
    idx = pd.DatetimeIndex(["2026-11-26 07:00", "2026-11-26 07:05"]).tz_localize("UTC")
    sutunlar = pd.MultiIndex.from_product([["AAA.IS", "BBB.IS"], ["Open", "High", "Low", "Close", "Volume"]])
    ham = pd.DataFrame(np.arange(20, dtype=float).reshape(2, 10), index=idx, columns=sutunlar)
    ham.loc[idx[1], ("BBB.IS", "Close")] = np.nan          # eksik mum atlanmalı
    t = anlik._uzun_tablo(ham, ["AAA.IS", "BBB.IS", "YOK.IS"])
    assert set(t["kod"]) == {"AAA", "BBB"}
    assert len(t) == 3
    assert t["zaman"].iloc[0] == pd.Timestamp("2026-11-26 10:00")   # UTC → İstanbul


def test_anlik_tablo_onceki_kapanisa_gore_degisim():
    t = anlik.anlik_tablo(sahte_mumlar())
    a = t.loc["AAA"]
    assert a["son_fiyat"] == 112 and a["onceki_kapanis"] == 102
    assert a["degisim"] == pytest.approx(112 / 102 - 1)
    assert a["gun_acilis"] == 109.5 and a["gun_yuksek"] == 113 and a["gun_dusuk"] == 109
    assert a["gun_hacim"] == 300 and a["zaman"] == pd.Timestamp("2026-11-26 10:10")


def test_bugunku_mum():
    m = anlik.bugunku_mum(sahte_mumlar(), "BBB")
    assert m.name == pd.Timestamp("2026-11-26")
    assert (m["acilis"], m["kapanis"], m["yuksek"], m["dusuk"]) == (59.5, 62, 63, 59)
    assert anlik.bugunku_mum(sahte_mumlar(), "YOK") is None


class _SahteKova:
    def __init__(self, dosyalar):
        self.dosyalar = dosyalar

    def download(self, yol):
        return self.dosyalar[yol]

    def upload(self, yol, veri, secenek=None):
        self.dosyalar[yol] = veri

    def remove(self, yollar):
        for y in yollar:
            self.dosyalar.pop(y, None)


def test_alt_kume_yukleme_diger_dosyalari_korur(tmp_path, monkeypatch):
    (tmp_path / "anlik").mkdir()
    (tmp_path / "anlik" / "anlik.parquet").write_bytes(b"yeni")
    eski = {"fiyat/A.parquet": "h1", "anlik/anlik.parquet": "eski"}
    kova = _SahteKova({bulut.MANIFEST: json.dumps({"dosyalar": eski}).encode()})

    class _Istemci:
        class storage:
            @staticmethod
            def from_(_):
                return kova

    monkeypatch.setattr(bulut, "istemci", lambda yazma=False: _Istemci)
    assert bulut.yukle(tmp_path, klasorler=["anlik"]) == 1
    yeni = json.loads(kova.dosyalar[bulut.MANIFEST])["dosyalar"]
    assert yeni["fiyat/A.parquet"] == "h1"                     # dokunulmadı
    assert yeni["anlik/anlik.parquet"] != "eski"
    assert kova.dosyalar["anlik/anlik.parquet"] == b"yeni"


def test_grafik_cevabi_tablo_istanbul_saati_ve_bos_mum():
    """Yahoo chart cevabı: UTC zaman damgası İstanbul saatine çevrilir, kapanışı boş mum atılır."""
    cevap = {"chart": {"result": [{
        "timestamp": [1795695600, 1795695660, 1795695720],   # 2026-11-26 12:20-12:22 UTC
        "indicators": {"quote": [{"open": [10, 11, None], "high": [10.5, 11.5, None], "low": [9.5, 10.5, None],
                                  "close": [10.2, 11.2, None], "volume": [100, 200, None]}]}}]}}
    t = anlik._grafik_cevabi_tablo(cevap, "THYAO.IS")
    assert len(t) == 2 and set(t["kod"]) == {"THYAO"}
    assert t["zaman"].iloc[0] == pd.Timestamp("2026-11-26 15:20")
    assert t["kapanis"].tolist() == [10.2, 11.2]


def test_grafik_cevabi_bos_ya_da_hatali():
    assert anlik._grafik_cevabi_tablo({"chart": {"result": None}}, "X.IS").empty
    assert anlik._grafik_cevabi_tablo({}, "X.IS").empty
