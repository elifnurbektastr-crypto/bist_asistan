"""İleri test kayıtları: günlük tahmin dosyaları ve parmak izi (SHA-256) zinciri.

Her günün tahmin dosyasının parmak izi, bir önceki günün zincir değeriyle birleştirilip
yeniden parmak izi alınır. Böylece geçmişteki tek bir sayı bile değişirse o günden
itibaren tüm zincir bozulur ve `dogrula()` bunu tarihiyle birlikte yakalar.
Kayıtlar her gün git'e commit'lenir; git geçmişi ikinci bir zaman damgası sağlar.
"""

import hashlib
from pathlib import Path

import pandas as pd

from src import config

IT_DIZINI = config.KOK_DIZIN / "ileri_test"
BASLANGIC_HASH = "0" * 64
ZINCIR_SUTUNLARI = ["tarih", "dosya", "dosya_hash", "onceki_hash", "zincir_hash",
                    "model_surumu", "olusturma_zamani", "satir"]


def dosya_hash(yol: Path) -> str:
    """Dosyanın baytlarından SHA-256 parmak izi."""
    return hashlib.sha256(Path(yol).read_bytes()).hexdigest()


def zincir_hash(onceki: str, tarih: str, d_hash: str) -> str:
    """Önceki zincir değeri + tarih + dosya parmak izinden yeni zincir değeri."""
    return hashlib.sha256(f"{onceki}|{tarih}|{d_hash}".encode()).hexdigest()


# İki tür kayıt aynı mekanizmayı kullanır:
#   tahmin : akşam, kapanıştan sonra (son geçerli zaman: ertesi seans açılışı)
#   acilis : sabah, seans açıldıktan sonra açılış fiyatları (son geçerli zaman: aynı gün seans sonu)
TURLER = {
    "tahmin": {"klasor": "tahminler", "zincir": "zincir.csv"},
    "acilis": {"klasor": "acilislar", "zincir": "acilis_zincir.csv"},
}


def zinciri_oku(dizin: Path = IT_DIZINI, tur: str = "tahmin") -> pd.DataFrame:
    """Zincir dosyasını okur; yoksa boş tablo döner."""
    yol = dizin / TURLER[tur]["zincir"]
    if not yol.exists():
        return pd.DataFrame(columns=ZINCIR_SUTUNLARI)
    return pd.read_csv(yol, dtype=str)


def son_gecerli_zaman(tarih, tur: str = "tahmin") -> pd.Timestamp:
    """Bir kaydın en geç ne zamana kadar yapılabileceği.

    tahmin: ertesi hafta içi günü 09:55 (seans açıldıktan sonra yapılan tahmin açılışı görmüş olabilir)
    acilis: aynı gün 18:00 (seans bittikten sonra 'sabah gördüm' denemez)
    """
    if tur == "acilis":
        return pd.Timestamp(f"{pd.Timestamp(tarih).date()} 18:00", tz=config.SAAT_DILIMI)
    sonraki = pd.Timestamp(tarih) + pd.offsets.BDay(1)
    return pd.Timestamp(f"{sonraki.date()} 09:55", tz=config.SAAT_DILIMI)


def tahmin_kaydet(tahmin: pd.DataFrame, tarih, model_surumu: str,
                  simdi: pd.Timestamp | None = None, dizin: Path = IT_DIZINI, tur: str = "tahmin") -> Path:
    """Bir günün tahminlerini yazar ve zincire ekler. Var olan kaydın üzerine yazmaz.

    Hata verdiği durumlar: aynı gün zaten kayıtlı, tarih zincirdeki son tarihten eski,
    ya da son geçerli zaman (ertesi seans açılışı) geçmiş.
    """
    tarih = pd.Timestamp(tarih).strftime("%Y-%m-%d")
    simdi = simdi or pd.Timestamp.now(tz=config.SAAT_DILIMI)
    if simdi > son_gecerli_zaman(tarih, tur):
        raise ValueError(f"{tarih} için kayıt süresi doldu ({son_gecerli_zaman(tarih, tur)}).")
    if tur == "acilis" and simdi.date() != pd.Timestamp(tarih).date():
        raise ValueError(f"{tarih} açılış kaydı sadece o gün yapılabilir.")
    klasor, zincir_adi = TURLER[tur]["klasor"], TURLER[tur]["zincir"]
    zincir = zinciri_oku(dizin, tur)
    if len(zincir) and tarih <= zincir["tarih"].iloc[-1]:
        raise ValueError(f"{tarih} zincirdeki son tarihten ({zincir['tarih'].iloc[-1]}) yeni değil.")
    yol = dizin / klasor / f"{tarih}.csv"
    if yol.exists():
        raise FileExistsError(f"{yol} zaten var; üzerine yazılmaz.")

    yol.parent.mkdir(parents=True, exist_ok=True)
    tahmin.to_csv(yol, index=False, float_format="%.6f", lineterminator="\n", encoding="utf-8")
    d_hash = dosya_hash(yol)
    onceki = zincir["zincir_hash"].iloc[-1] if len(zincir) else BASLANGIC_HASH
    satir = pd.DataFrame([{
        "tarih": tarih, "dosya": f"{klasor}/{tarih}.csv", "dosya_hash": d_hash,
        "onceki_hash": onceki, "zincir_hash": zincir_hash(onceki, tarih, d_hash),
        "model_surumu": model_surumu, "olusturma_zamani": simdi.isoformat(timespec="seconds"),
        "satir": len(tahmin),
    }])
    zincir_yolu = dizin / zincir_adi
    satir.to_csv(zincir_yolu, mode="a", header=not zincir_yolu.exists(), index=False, lineterminator="\n")
    return yol


def dogrula(dizin: Path = IT_DIZINI, turler=tuple(TURLER)) -> list[str]:
    """Tüm zincirleri baştan sona yeniden hesaplar; sorunları listeler (boşsa her şey sağlam)."""
    sorunlar = []
    for tur in turler:
        sorunlar += [f"[{tur}] {s}" for s in _zincir_dogrula(dizin, tur)]
    return sorunlar


def _zincir_dogrula(dizin: Path, tur: str) -> list[str]:
    """Tek bir zinciri doğrular."""
    sorunlar = []
    zincir = zinciri_oku(dizin, tur)
    onceki = BASLANGIC_HASH
    for _, s in zincir.iterrows():
        yol = dizin / s["dosya"]
        if not yol.exists():
            sorunlar.append(f"{s['tarih']}: dosya kayıp ({s['dosya']})")
            continue
        d_hash = dosya_hash(yol)
        if d_hash != s["dosya_hash"]:
            sorunlar.append(f"{s['tarih']}: tahmin dosyası DEĞİŞTİRİLMİŞ (parmak izi uyuşmuyor)")
        if s["onceki_hash"] != onceki or zincir_hash(onceki, s["tarih"], s["dosya_hash"]) != s["zincir_hash"]:
            sorunlar.append(f"{s['tarih']}: zincir kırık (zincir kaydı değiştirilmiş)")
        try:
            olusturma = pd.Timestamp(s["olusturma_zamani"])
            if olusturma > son_gecerli_zaman(s["tarih"], tur):
                sorunlar.append(f"{s['tarih']}: kayıt süresi geçtikten sonra oluşturulmuş")
        except ValueError:
            sorunlar.append(f"{s['tarih']}: oluşturma zamanı okunamadı")
        onceki = s["zincir_hash"]
    kayitli = set(zincir["dosya"])
    klasor = TURLER[tur]["klasor"]
    for yol in sorted((dizin / klasor).glob("*.csv")):
        if f"{klasor}/{yol.name}" not in kayitli:
            sorunlar.append(f"{yol.stem}: zincirde olmayan dosya")
    return sorunlar


def tum_tahminler(dizin: Path = IT_DIZINI, tur: str = "tahmin") -> pd.DataFrame:
    """Zincirdeki bütün günlerin kayıtlarını tek tabloda birleştirir."""
    zincir = zinciri_oku(dizin, tur)
    if zincir.empty:
        return pd.DataFrame()
    parcalar = [pd.read_csv(dizin / s["dosya"]).assign(tahmin_tarihi=pd.Timestamp(s["tarih"]),
                                                       model_surumu=s["model_surumu"])
                for _, s in zincir.iterrows()]
    return pd.concat(parcalar, ignore_index=True)
