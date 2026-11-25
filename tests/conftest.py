"""Testlerde ortak kullanılan sahte (sentetik) veriler. İnternete bağlanılmaz."""

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _supabase_kapali(monkeypatch):
    """Testler yerel SQLite deposunu kullanır; boş ortam değişkeni .env'deki değeri gölgeler."""
    for ad in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_SECRET_KEY", "BIST_BULUT"):
        monkeypatch.setenv(ad, "")


@pytest.fixture
def yf_ornek() -> pd.DataFrame:
    """yfinance biçiminde 8 günlük sahte veri.

    Gerçekte olan:
      - 2. gün (03.01) 2 TL temettü (bölünmeden önce)
      - 4. gün (05.01) 2:1 bölünme: ham fiyat 104 -> 52
      - 6. gün (09.01) 1 TL temettü (bölünmeden sonra)
    yfinance 'Close' bölünmeye göre düzeltilmiş verir: bölünme öncesi fiyatlar /2.
    """
    tarihler = pd.DatetimeIndex(
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05",
         "2024-01-08", "2024-01-09", "2024-01-10", "2024-01-11"]
    ).tz_localize("Europe/Istanbul")
    ham_kapanis = [100.0, 102.0, 104.0, 52.0, 53.0, 54.0, 55.0, 56.0]
    bolunme = [0, 0, 0, 2.0, 0, 0, 0, 0]
    ham_temettu = [0, 2.0, 0, 0, 0, 1.0, 0, 0]

    sonraki_carpan = [2, 2, 2, 1, 1, 1, 1, 1]   # bölünme sonrası bazına çevirme
    close = [k / c for k, c in zip(ham_kapanis, sonraki_carpan)]
    temettu = [t / c for t, c in zip(ham_temettu, sonraki_carpan)]

    # Adj Close: her temettü için öncesindeki fiyatları (1 - temettü/önceki kapanış) ile çarp
    adj = pd.Series(close, index=tarihler)
    for i, t in enumerate(temettu):
        if t > 0:
            adj.iloc[:i] *= 1 - t / close[i - 1]

    return pd.DataFrame({
        "Open": close, "High": [c * 1.01 for c in close], "Low": [c * 0.99 for c in close],
        "Close": close, "Adj Close": adj.values,
        "Volume": [1000.0 * c for c in sonraki_carpan],  # yfinance hacmi de bölünme bazında
        "Dividends": temettu, "Stock Splits": bolunme,
    }, index=tarihler)
