"""Uygulama verisi deposu: duyurular ve kullanıcı geri bildirimleri.

Kullanıcı sayfası ve admin sayfası aynı depoyu kullanır. .env'de (ya da bulutta Secrets'ta)
Supabase bilgileri varsa Supabase (PostgreSQL), yoksa yerel SQLite dosyası (data/uygulama.db).
Arayüz: duyuru_ekle / aktif_duyurular / tum_duyurular / duyuru_kapat,
        geri_bildirim_ekle / geri_bildirimler.
"""

import sqlite3
from pathlib import Path

import pandas as pd

from src import config

DB_YOLU = config.VERI_DIZINI / "uygulama.db"
NOT_SINIRI = 200
DUYURU_TURLERI = ("bilgi", "uyari", "onemli")


def duyuru_dogrula(baslik: str, metin: str, tur: str) -> None:
    """İki depo için ortak kurallar (Supabase'de aynıları tablo kısıtı olarak da var)."""
    if tur not in DUYURU_TURLERI:
        raise ValueError(f"Duyuru türü {DUYURU_TURLERI} içinden olmalı.")
    if not baslik.strip() or not metin.strip():
        raise ValueError("Başlık ve metin boş olamaz.")


def geri_bildirim_hazirla(puan: int, notu: str) -> str:
    """Puanı denetler, notu kırpar (en fazla 200 karakter)."""
    if puan not in (-1, 1):
        raise ValueError("Puan +1 ya da -1 olmalı.")
    return (notu or "").strip()[:NOT_SINIRI]


class SQLiteDepo:
    """Yerel SQLite deposu. Her çağrı kendi bağlantısını açar (Streamlit çoklu iş parçacığı için güvenli)."""

    def __init__(self, yol: Path = DB_YOLU):
        self.yol = Path(yol)
        self.yol.parent.mkdir(parents=True, exist_ok=True)
        with self._baglan() as b:
            b.executescript("""
                CREATE TABLE IF NOT EXISTS duyurular (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    baslik TEXT NOT NULL, metin TEXT NOT NULL,
                    tur TEXT NOT NULL DEFAULT 'bilgi',
                    olusturma TEXT NOT NULL, bitis TEXT, aktif INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS geri_bildirimler (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    zaman TEXT NOT NULL, sekme TEXT NOT NULL,
                    puan INTEGER NOT NULL CHECK (puan IN (-1, 1)), notu TEXT);
            """)

    def _baglan(self) -> sqlite3.Connection:
        return sqlite3.connect(self.yol)

    @staticmethod
    def _simdi() -> str:
        return pd.Timestamp.now(tz=config.SAAT_DILIMI).isoformat(timespec="seconds")

    # --- Duyurular ---
    def duyuru_ekle(self, baslik: str, metin: str, tur: str = "bilgi", bitis: str | None = None) -> int:
        """Yeni duyuru ekler; bitis (YYYY-AA-GG) verilirse o günden sonra gösterilmez."""
        duyuru_dogrula(baslik, metin, tur)
        with self._baglan() as b:
            imlec = b.execute("INSERT INTO duyurular (baslik, metin, tur, olusturma, bitis) VALUES (?, ?, ?, ?, ?)",
                              (baslik.strip(), metin.strip(), tur, self._simdi(), bitis))
            return int(imlec.lastrowid)

    def tum_duyurular(self) -> pd.DataFrame:
        with self._baglan() as b:
            return pd.read_sql_query("SELECT * FROM duyurular ORDER BY id DESC", b)

    def aktif_duyurular(self, bugun: str | None = None) -> pd.DataFrame:
        """Aktif ve süresi dolmamış duyurular (en yeni önce)."""
        bugun = bugun or pd.Timestamp.now(tz=config.SAAT_DILIMI).strftime("%Y-%m-%d")
        with self._baglan() as b:
            return pd.read_sql_query(
                "SELECT * FROM duyurular WHERE aktif = 1 AND (bitis IS NULL OR bitis >= ?) ORDER BY id DESC",
                b, params=(bugun,))

    def duyuru_kapat(self, duyuru_id: int) -> None:
        with self._baglan() as b:
            b.execute("UPDATE duyurular SET aktif = 0 WHERE id = ?", (int(duyuru_id),))

    # --- Geri bildirim ---
    def geri_bildirim_ekle(self, sekme: str, puan: int, notu: str = "") -> int:
        """👍 (+1) / 👎 (-1) ve en fazla 200 karakterlik kısa not."""
        notu = geri_bildirim_hazirla(puan, notu)
        with self._baglan() as b:
            imlec = b.execute("INSERT INTO geri_bildirimler (zaman, sekme, puan, notu) VALUES (?, ?, ?, ?)",
                              (self._simdi(), sekme, puan, notu or None))
            return int(imlec.lastrowid)

    def geri_bildirimler(self) -> pd.DataFrame:
        with self._baglan() as b:
            return pd.read_sql_query("SELECT * FROM geri_bildirimler ORDER BY id DESC", b)


DUYURU_SUTUNLARI = ["id", "baslik", "metin", "tur", "olusturma", "bitis", "aktif"]
GERI_BILDIRIM_SUTUNLARI = ["id", "zaman", "sekme", "puan", "notu"]


class SupabaseDepo:
    """Supabase (PostgreSQL) deposu: SQLiteDepo ile aynı arayüz.

    Uygulamanın anahtarıyla (publishable) satır düzeyi güvenlik geçerlidir: sadece aktif duyurular
    okunur, geri bildirim eklenir ama okunamaz. Admin secret anahtarla her şeyi görür.
    Kurulum: supabase/kurulum.sql
    """

    def __init__(self, istemci=None):
        from src import bulut
        self.db = istemci or bulut.istemci()

    @staticmethod
    def _tablo(satirlar: list[dict], sutunlar: list[str]) -> pd.DataFrame:
        return pd.DataFrame(satirlar, columns=sutunlar)

    def duyuru_ekle(self, baslik: str, metin: str, tur: str = "bilgi", bitis: str | None = None) -> int:
        duyuru_dogrula(baslik, metin, tur)
        cevap = self.db.table("duyurular").insert(
            {"baslik": baslik.strip(), "metin": metin.strip(), "tur": tur, "bitis": bitis}).execute()
        return int(cevap.data[0]["id"]) if cevap.data else 0

    def tum_duyurular(self) -> pd.DataFrame:
        satirlar = self.db.table("duyurular").select("*").order("id", desc=True).execute().data
        return self._tablo(satirlar, DUYURU_SUTUNLARI)

    def aktif_duyurular(self, bugun: str | None = None) -> pd.DataFrame:
        bugun = bugun or pd.Timestamp.now(tz=config.SAAT_DILIMI).strftime("%Y-%m-%d")
        satirlar = self.db.table("duyurular").select("*").eq("aktif", True).order("id", desc=True).execute().data
        tablo = self._tablo(satirlar, DUYURU_SUTUNLARI)
        return tablo[tablo["bitis"].isna() | (tablo["bitis"].astype(str) >= bugun)].reset_index(drop=True)

    def duyuru_kapat(self, duyuru_id: int) -> None:
        self.db.table("duyurular").update({"aktif": False}).eq("id", int(duyuru_id)).execute()

    def geri_bildirim_ekle(self, sekme: str, puan: int, notu: str = "") -> int:
        from postgrest.types import ReturnMethod
        notu = geri_bildirim_hazirla(puan, notu)
        # 'minimal': eklenen satır geri istenmez (uygulama anahtarının okuma izni yok)
        self.db.table("geri_bildirimler").insert(
            {"sekme": sekme[:40], "puan": puan, "notu": notu or None}, returning=ReturnMethod.minimal).execute()
        return 0

    def geri_bildirimler(self) -> pd.DataFrame:
        satirlar = self.db.table("geri_bildirimler").select("*").order("id", desc=True).execute().data
        return self._tablo(satirlar, GERI_BILDIRIM_SUTUNLARI)


def depo_al() -> "SQLiteDepo | SupabaseDepo":
    """Supabase bilgileri tanımlıysa Supabase, değilse yerel SQLite deposu."""
    from src import bulut
    a = bulut.ayarlar()
    if a["url"] and (a["secret"] or a["publishable"]):
        return SupabaseDepo()
    return SQLiteDepo()
