"""İleri test: değişmezlik zinciri, süre kuralı, sonuç hesabı, model dondurma, Excel."""

import numpy as np
import pandas as pd
import pytest

from src.ileri_test import excel, kayit, sonuc
from src.ileri_test import model as it_model

TZ = "Europe/Istanbul"


def ornek_tahmin(n: int = 3, tohum: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(tohum)
    return pd.DataFrame({"kod": [f"H{i}" for i in range(n)], "yukselis_olasiligi": rng.random(n),
                         "sinyal": "zayıf al", "beklenen_vol_20": 0.3, "kapanis": 100.0,
                         "hisseye_ozel_model": True})


def kaydet(dizin, tarih, saat="19:00"):
    return kayit.tahmin_kaydet(ornek_tahmin(tohum=hash(tarih) % 100), tarih, "v1",
                               simdi=pd.Timestamp(f"{tarih} {saat}", tz=TZ), dizin=dizin)


def test_zincir_saglam_kayit(tmp_path):
    for t in ["2026-11-23", "2026-11-24", "2026-11-25"]:
        kaydet(tmp_path, t)
    assert kayit.dogrula(tmp_path) == []
    zincir = kayit.zinciri_oku(tmp_path)
    assert zincir["onceki_hash"].iloc[0] == kayit.BASLANGIC_HASH
    assert zincir["onceki_hash"].iloc[1] == zincir["zincir_hash"].iloc[0]
    assert len(kayit.tum_tahminler(tmp_path)) == 9


def test_tek_sayi_degisirse_yakalanir(tmp_path):
    for t in ["2026-11-23", "2026-11-24"]:
        kaydet(tmp_path, t)
    yol = tmp_path / "tahminler" / "2026-11-23.csv"
    metin = yol.read_text(encoding="utf-8").splitlines()
    metin[1] = metin[1].replace("0.", "0.9", 1)   # bir olasılığı değiştir
    yol.write_text("\n".join(metin) + "\n", encoding="utf-8")
    sorunlar = kayit.dogrula(tmp_path)
    assert any("2026-11-23" in s and "DEĞİŞTİRİLMİŞ" in s for s in sorunlar)


def test_zincir_kaydi_ile_oynanirsa_yakalanir(tmp_path):
    """Dosya değiştirilip parmak izi de zincirde güncellense bile zincir kırılır."""
    for t in ["2026-11-23", "2026-11-24"]:
        kaydet(tmp_path, t)
    yol = tmp_path / "tahminler" / "2026-11-23.csv"
    yol.write_text(yol.read_text(encoding="utf-8").replace("H0", "H9"), encoding="utf-8")
    zincir = kayit.zinciri_oku(tmp_path)
    zincir.loc[0, "dosya_hash"] = kayit.dosya_hash(yol)
    zincir.to_csv(tmp_path / "zincir.csv", index=False, lineterminator="\n")
    assert any("zincir kırık" in s for s in kayit.dogrula(tmp_path))


def test_uzerine_yazilmaz_ve_geriye_gidilmez(tmp_path):
    kaydet(tmp_path, "2026-11-24")
    with pytest.raises(ValueError):
        kaydet(tmp_path, "2026-11-24")
    with pytest.raises(ValueError):
        kaydet(tmp_path, "2026-11-23")


def test_seans_acildiktan_sonra_tahmin_reddedilir(tmp_path):
    # Cuma'nın tahmini en geç Pazartesi 09:55'e kadar yapılabilir
    assert kayit.son_gecerli_zaman("2026-11-20") == pd.Timestamp("2026-11-23 09:55", tz=TZ)
    kayit.tahmin_kaydet(ornek_tahmin(), "2026-11-20", "v1",
                        simdi=pd.Timestamp("2026-11-22 12:00", tz=TZ), dizin=tmp_path)
    with pytest.raises(ValueError, match="süresi doldu"):
        kayit.tahmin_kaydet(ornek_tahmin(), "2026-11-23", "v1",
                            simdi=pd.Timestamp("2026-11-24 10:30", tz=TZ), dizin=tmp_path)


def test_zincirde_olmayan_dosya_yakalanir(tmp_path):
    kaydet(tmp_path, "2026-11-24")
    ornek_tahmin().to_csv(tmp_path / "tahminler" / "2026-11-25.csv", index=False)
    assert any("zincirde olmayan" in s for s in kayit.dogrula(tmp_path))


def fiyat(acilislar, baslangic="2026-11-02"):
    idx = pd.bdate_range(baslangic, periods=len(acilislar))
    a = np.array(acilislar, dtype=float)
    return pd.DataFrame({"duz_acilis": a, "duz_kapanis": a, "kapanis": a, "duz_yuksek": a,
                         "duz_dusuk": a, "acilis": a, "yuksek": a, "dusuk": a, "hacim": 1.0,
                         "temettu": 0.0, "temettu_duz": 0.0, "bolunme": 0.0}, index=idx)


def test_sonuc_ertesi_gun_acilistan_5_gun():
    veri = {"AAA.IS": fiyat([100, 101, 102, 103, 104, 105, 106, 110, 90])}
    tahmin = pd.DataFrame({"kod": ["AAA", "AAA"], "yukselis_olasiligi": [0.7, 0.3],
                           "sinyal": ["güçlü al", "al değil"],
                           "tahmin_tarihi": pd.to_datetime(["2026-11-02", "2026-11-06"])})
    s = sonuc.sonuclari_hesapla(tahmin, veri)
    ilk = s.iloc[0]
    assert ilk["giris_tarihi"] == pd.Timestamp("2026-11-03")
    assert ilk["gerceklesen_getiri"] == pytest.approx(106 / 101 - 1)
    assert ilk["model_dogru"] == 1.0 and ilk["durum"] == "tamamlandı"
    # 06.11 (Cuma) tahmini: giriş 09.11 açılışı (105), veri 12.11'de bitiyor -> 4. gündeyiz
    ikinci = s.iloc[1]
    assert ikinci["durum"] == "4. gün" and ikinci["gecen_gun"] == 4
    assert ikinci["gun_1_getiri"] == pytest.approx(105 / 105 - 1)   # 09.11 kapanışı
    assert ikinci["gun_3_getiri"] == pytest.approx(110 / 105 - 1)   # 11.11 kapanışı
    assert ikinci["gun_4_getiri"] == pytest.approx(90 / 105 - 1)    # 12.11 kapanışı
    assert ikinci["anlik_getiri"] == pytest.approx(ikinci["gun_4_getiri"])
    assert ilk["anlik_getiri"] == pytest.approx(ilk["gerceklesen_getiri"])
    o = sonuc.ozet(s)
    assert o["tamamlanan"] == 1 and o["guclu_al_isabeti"] == 1.0


@pytest.fixture(scope="module")
def kucuk_tablo():
    from src.features.indicators import veri_seti_olustur
    from tests.test_indicators import sahte_hisse
    veri = {f"H{i}.IS": sahte_hisse(n=900, tohum=i) for i in range(3)}
    return veri, veri_seti_olustur(veri, sahte_hisse(n=900, tohum=99))


def test_model_dondur_yukle_ve_degisiklik_yakalama(tmp_path, kucuk_tablo):
    veri, tablo = kucuk_tablo
    surum, mdizin = tmp_path / "model_surumu.json", tmp_path / "model"
    bilgi = it_model.dondur(tablo, surum_dosyasi=surum, model_dizini=mdizin)
    with pytest.raises(FileExistsError):
        it_model.dondur(tablo, surum_dosyasi=surum, model_dizini=mdizin)
    model, bilgi2 = it_model.yukle(surum, mdizin)
    assert bilgi2["sha256"] == bilgi["sha256"]

    son = tablo.index.get_level_values("tarih").max()
    gun = tablo.xs(son, level="tarih").dropna(subset=["getiri_60"])
    gun.index = pd.MultiIndex.from_arrays([gun.index], names=["kod"])
    t = it_model.tahmin_uret(model, bilgi2, gun, pd.Series(100.0, index=gun.index.get_level_values("kod")))
    assert len(t) == 3 and t["yukselis_olasiligi"].between(0, 1).all()

    with open(mdizin / bilgi["dosya"], "ab") as f:
        f.write(b"x")
    with pytest.raises(it_model.ModelDegisti):
        it_model.yukle(surum, mdizin)


def test_excel_uretilir_ve_korumali(tmp_path, kucuk_tablo):
    from openpyxl import load_workbook
    veri, _ = kucuk_tablo
    tahmin = ornek_tahmin().assign(tahmin_tarihi=pd.Timestamp("2023-06-01"), model_surumu="v1")
    yol = excel.excel_uret(tahmin, veri, pd.DataFrame({"tarih": ["2023-06-01"]}), [],
                           {"model": "m", "surum": "v1", "egitim_son_tarih": "2023-05-01"},
                           yol=tmp_path / "it.xlsx")
    kitap = load_workbook(yol)
    assert kitap.sheetnames == ["Özet", "Tahminler", "Gözlemler", "Hisse Özeti",
                                "Hisse Kartı (genel bilgi)", "Günlük", "Bütünlük"]
    assert all(ws.protection.sheet for ws in kitap.worksheets)
    assert kitap["Özet"]["B3"].value.startswith("✓")   # Kayıt bütünlüğü satırı


def test_acilis_kaydi_sadece_o_gun_seans_icinde(tmp_path):
    tablo = pd.DataFrame({"kod": ["A"], "acilis": [10.0], "anlik_fiyat": [10.1], "kayit_saati": ["10:30:00"]})
    kayit.tahmin_kaydet(tablo, "2026-11-26", "-", simdi=pd.Timestamp("2026-11-26 10:30", tz=TZ),
                        dizin=tmp_path, tur="acilis")
    with pytest.raises(ValueError):   # seans bittikten sonra
        kayit.tahmin_kaydet(tablo, "2026-11-27", "-", simdi=pd.Timestamp("2026-11-27 18:30", tz=TZ),
                            dizin=tmp_path, tur="acilis")
    with pytest.raises(ValueError):   # başka bir gün için
        kayit.tahmin_kaydet(tablo, "2026-11-27", "-", simdi=pd.Timestamp("2026-11-28 11:00", tz=TZ),
                            dizin=tmp_path, tur="acilis")
    assert kayit.dogrula(tmp_path) == []
    assert (tmp_path / "acilis_zincir.csv").exists() and not (tmp_path / "zincir.csv").exists()


def test_bugunku_satirlar_ve_gozlemler():
    from src.ileri_test.acilis import bugunku_satirlar
    idx = pd.DatetimeIndex(["2026-11-25", "2026-11-26"]).tz_localize(TZ)
    ham = {"AAA.IS": pd.DataFrame({"Open": [9.0, 10.0], "Close": [9.5, 10.2]}, index=idx)}
    t = bugunku_satirlar(ham, pd.Timestamp("2026-11-26 10:30"))
    assert t.to_dict("records") == [{"kod": "AAA", "acilis": 10.0, "anlik_fiyat": 10.2}]

    veri = {"AAA.IS": fiyat([10.0, 11.0], baslangic="2026-11-26")}
    acilislar = t.assign(tahmin_tarihi=pd.Timestamp("2026-11-26"), kayit_saati="10:30:00")
    tahmin = pd.DataFrame({"kod": ["AAA"], "kapanis": [10.0], "tahmin_tarihi": [pd.Timestamp("2026-11-26")]})
    g = sonuc.gozlemler(acilislar, tahmin, veri)
    assert g.loc[0, "sabah_acilis"] == 10.0 and g.loc[0, "resmi_acilis"] == 10.0
    assert g.loc[0, "uyari"] == ""
