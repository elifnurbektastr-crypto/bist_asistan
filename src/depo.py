"""Uygulama verisi deposu: duyurular ve kullanıcı geri bildirimleri.

Kullanıcı sayfası ve admin sayfası aynı depoyu kullanır. Şimdilik yerel SQLite dosyası
(data/uygulama.db); yayına alınırken (Aşama 6) aynı arayüzle Supabase'e geçilecek.
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
        if tur not in DUYURU_TURLERI:
            raise ValueError(f"Duyuru türü {DUYURU_TURLERI} içinden olmalı.")
        if not baslik.strip() or not metin.strip():
            raise ValueError("Başlık ve metin boş olamaz.")
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
        if puan not in (-1, 1):
            raise ValueError("Puan +1 ya da -1 olmalı.")
        notu = (notu or "").strip()[:NOT_SINIRI]
        with self._baglan() as b:
            imlec = b.execute("INSERT INTO geri_bildirimler (zaman, sekme, puan, notu) VALUES (?, ?, ?, ?)",
                              (self._simdi(), sekme, puan, notu or None))
            return int(imlec.lastrowid)

    def geri_bildirimler(self) -> pd.DataFrame:
        with self._baglan() as b:
            return pd.read_sql_query("SELECT * FROM geri_bildirimler ORDER BY id DESC", b)


def depo_al() -> SQLiteDepo:
    """Ortama göre depoyu seçer. (Aşama 6: SUPABASE_URL tanımlıysa Supabase deposu.)"""
    return SQLiteDepo()
