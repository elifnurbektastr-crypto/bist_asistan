"""fetch.py'deki saf dönüşümlerin testleri."""

import pandas as pd
import pytest

from src.data.fetch import (_evds_tablosunu_duzenle, artimli_birlestir, standartlastir,
                            tamamlanmamis_cubugu_at)


def test_ham_fiyat_bolunme_oncesi_geri_kazanilir(yf_ornek):
    df = standartlastir(yf_ornek)
    assert df["kapanis"].tolist() == pytest.approx([100, 102, 104, 52, 53, 54, 55, 56])


def test_ham_hacim_bolunme_oncesi_geri_kazanilir(yf_ornek):
    df = standartlastir(yf_ornek)
    assert df["hacim"].tolist() == pytest.approx([1000] * 8)


def test_temettu_o_gunku_ve_bugunku_baz(yf_ornek):
    df = standartlastir(yf_ornek)
    assert df.loc["2024-01-03", "temettu"] == pytest.approx(2.0)      # gerçekte ödenen
    assert df.loc["2024-01-03", "temettu_duz"] == pytest.approx(1.0)  # bugünkü hisse bazında
    assert df.loc["2024-01-09", "temettu"] == pytest.approx(1.0)


def test_duzeltilmis_seride_bolunme_sicramasi_yok(yf_ornek):
    df = standartlastir(yf_ornek)
    getiri = df["duz_kapanis"].pct_change().dropna()
    assert getiri.abs().max() < 0.05   # ham seride bölünme günü -%50


def test_saat_dilimi_atilir_ve_siralanir(yf_ornek):
    df = standartlastir(yf_ornek.iloc[::-1])
    assert df.index.tz is None
    assert df.index.is_monotonic_increasing
    assert df.index[0] == pd.Timestamp("2024-01-02")


def test_eksik_aksiyon_sutunlari_sifirla_doldurulur(yf_ornek):
    df = standartlastir(yf_ornek.drop(columns=["Dividends", "Stock Splits", "Adj Close"]))
    assert (df["temettu"] == 0).all() and (df["bolunme"] == 0).all()


@pytest.mark.parametrize("saat, satir", [("15:00", 7), ("19:00", 8)])
def test_tamamlanmamis_cubuk(yf_ornek, saat, satir):
    df = standartlastir(yf_ornek)
    simdi = pd.Timestamp(f"2024-01-11 {saat}", tz="Europe/Istanbul")
    assert len(tamamlanmamis_cubugu_at(df, simdi)) == satir


def test_artimli_birlestirme_uyumlu_veri(yf_ornek):
    df = standartlastir(yf_ornek)
    eski, yeni = df.iloc[:7], df.iloc[5:]
    birlesik = artimli_birlestir(eski, yeni)
    pd.testing.assert_frame_equal(birlesik, df)


def test_artimli_birlestirme_fiyat_farkinda_tam_indirme_ister(yf_ornek):
    df = standartlastir(yf_ornek)
    yeni = df.iloc[5:].copy()
    yeni["duz_kapanis"] *= 0.97   # yeni temettü yüzünden geçmiş düzeltme değişmiş gibi
    assert artimli_birlestir(df.iloc[:7], yeni) is None


def test_artimli_birlestirme_yeni_bolunmede_tam_indirme_ister(yf_ornek):
    df = standartlastir(yf_ornek)
    # eski veri 4. güne kadar; yeni parçada 5.01 bölünmesi var
    assert artimli_birlestir(df.iloc[:3], df.iloc[1:]) is None


def test_evds_aylik_tarih_ve_yayin_tarihi():
    ham = pd.DataFrame({"Tarih": ["2024-1", "2024-2"], "TP_FG_J0": ["1984.02", "2073.94"]})
    df = _evds_tablosunu_duzenle(ham, "TP.FG.J0", "tufe")
    assert df.index[0] == pd.Timestamp("2024-01-01")
    assert df["tufe"].iloc[1] == pytest.approx(2073.94)
    assert df["tufe_yayin_tarihi"].iloc[0] == pd.Timestamp("2024-02-03")


def test_devre_kesici_ust_uste_basarisizlikta_durur(monkeypatch, yf_ornek):
    from src.data import fetch
    denenen = []

    def sahte_indir(sembol, baslangic):
        denenen.append(sembol)
        return yf_ornek if sembol == "A" else None

    monkeypatch.setattr(fetch, "_tek_indir", sahte_indir)
    monkeypatch.setattr(fetch.time, "sleep", lambda _: None)
    sonuc = fetch._indir(["A", "B", "C", "D", "E", "F"], "2024-01-01")
    assert list(sonuc) == ["A"]
    assert denenen == ["A", "B", "C", "D"]   # 3 başarısızlıktan sonra E ve F denenmez


def test_tatil_satirlari_atilir_kur_serisine_dokunulmaz(yf_ornek):
    from src.data.fetch import tatil_satirlarini_at
    df = standartlastir(yf_ornek)
    df.loc["2024-01-08", "hacim"] = 0
    assert pd.Timestamp("2024-01-08") not in tatil_satirlarini_at(df).index
    kur = df.assign(hacim=0.0)   # döviz kurunda hacim hiç yok
    assert len(tatil_satirlarini_at(kur)) == len(kur)


def test_evds_parcalari_bosluksuz_ve_cakismasiz():
    from src.data.fetch import evds_parcalari
    parcalar = evds_parcalari("2015-01-01", "2021-06-30", 3)
    assert parcalar[0] == (pd.Timestamp("2015-01-01"), pd.Timestamp("2017-12-31"))
    assert parcalar[-1] == (pd.Timestamp("2021-01-01"), pd.Timestamp("2021-06-30"))
    for (_, son), (bas, _) in zip(parcalar, parcalar[1:]):
        assert bas == son + pd.Timedelta(days=1)


def test_ikinci_turda_basarisiz_semboller_yeniden_denenir(monkeypatch, yf_ornek):
    from src.data import fetch
    deneme_sayisi = {}

    def sahte_indir(sembol, baslangic):
        deneme_sayisi[sembol] = deneme_sayisi.get(sembol, 0) + 1
        if sembol == "A" and deneme_sayisi[sembol] == 1:
            return None          # ilk istek boş, ikincisi gelir
        return yf_ornek

    monkeypatch.setattr(fetch, "_tek_indir", sahte_indir)
    monkeypatch.setattr(fetch.time, "sleep", lambda _: None)
    assert set(fetch._indir(["A", "B", "C"], "2024-01-01")) == {"A", "B", "C"}
    assert deneme_sayisi == {"A": 2, "B": 1, "C": 1}


def test_tek_indir_aksiyon_sutunu_olmayan_endeksi_kabul_eder(monkeypatch, yf_ornek):
    from src.data import fetch
    endeks = yf_ornek.drop(columns=["Dividends", "Stock Splits"])

    class SahteTicker:
        def __init__(self, sembol): pass
        def history(self, **kw): return endeks

    monkeypatch.setattr(fetch.yf, "Ticker", SahteTicker)
    assert fetch._tek_indir("XU100.IS", "2024-01-01") is not None


@pytest.mark.parametrize("yazma, simdi, beklenen", [
    ("2024-01-11 15:00", "2024-01-11 16:00", True),    # seans sürerken: gün içi önbellek yeterli
    ("2024-01-11 15:00", "2024-01-11 19:00", False),   # seans kapandı, önbellek kapanıştan önce
    ("2024-01-11 18:45", "2024-01-11 19:00", True),    # kapanıştan sonra yazılmış
    ("2024-01-10 20:00", "2024-01-11 08:00", False),   # dünden kalma
])
def test_onbellek_tazeligi_seans_kapanisina_gore(tmp_path, monkeypatch, yazma, simdi, beklenen):
    from src.data import cache, fetch
    tz = "Europe/Istanbul"
    monkeypatch.setattr(cache, "guncelleme_tarihi",
                        lambda *a, **k: pd.Timestamp(yazma, tz=tz).tz_convert("UTC"))
    assert fetch._bugun_guncellendi_mi("X", simdi=pd.Timestamp(simdi, tz=tz)) == beklenen


def test_cevrimdisi_internete_gitmez(tmp_path, monkeypatch, yf_ornek):
    from src.data import cache, fetch
    cache.yaz(standartlastir(yf_ornek), "AAA.IS", dizin=tmp_path)
    monkeypatch.setattr(fetch, "_indir", lambda *a, **k: pytest.fail("internete gidilmemeli"))
    veri = fetch.fiyat_verisi(["AAA", "YOK"], dizin=tmp_path, cevrimdisi=True)
    assert list(veri) == ["AAA.IS"]
