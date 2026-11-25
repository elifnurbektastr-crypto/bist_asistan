# 📈 BIST Yatırım Araştırma Asistanı

BIST hisseleri için **veri analizi**, **makine öğrenmesi tahmini**, **strateji backtest'i** ve **LLM ajanını** tek bir uygulamada birleştiren bir araştırma asistanı.

Kullanıcı sohbet ekranına doğal dilde soru yazar, AI ajanı gerekli araçları kendisi çalıştırır ve sonucu Türkçe açıklar:

> 💬 *"THYAO için son 1 yılda 20/50 hareketli ortalama stratejisi al-ve-tut'u geçer miydi?"*
> 💬 *"ASELS'in volatilitesi son 3 ayda nasıl değişti, USD/TRY ile ilişkisi var mı?"*
> 💬 *"Modelin bu hafta GARAN için tahmini ne ve bu tahmine ne kadar güvenebilirim?"*

> ⚠️ **Yasal uyarı:** Bu proje eğitim ve portföy amaçlıdır. Yatırım tavsiyesi değildir. Gerçek para ile işlem yapmaz.

---

## 🎯 Projenin amacı

Fintech stajı başvuruları için şu becerileri tek bir projede göstermek:

| Beceri | Projede nerede? |
|---|---|
| Veri mühendisliği, API kullanımı | Veri katmanı (yfinance, TCMB EVDS) |
| Makine öğrenmesi ve dürüst model değerlendirme | Tahmin modülü |
| Finansal analiz, risk metrikleri | Backtest motoru |
| AI agent / LLM tool use | Sohbet ajanı |
| Ürün geliştirme, kullanıcı ihtiyacı analizi | Ücretsiz grafik/çizim aracı, Streamlit arayüzü ve canlı demo |

---

## 🏗️ Mimari

```
┌─────────────────────────────────────────────────────┐
│              Streamlit Arayüzü                      │
│ [Sohbet] [Grafik] [Analiz] [Backtest] [Model]       │
└──────────────────────┬──────────────────────────────┘
                       │
              ┌────────▼────────┐
              │   LLM Ajanı     │  ← soruyu anlar, araç seçer,
              │  (Claude API)   │    sonucu Türkçe açıklar
              └────────┬────────┘
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
 ┌────────────┐ ┌────────────┐ ┌────────────┐
 │ Veri       │ │ ML Tahmin  │ │ Backtest   │
 │ Katmanı    │ │ Modülü     │ │ Motoru     │
 └─────┬──────┘ └────────────┘ └────────────┘
       ▼
 yfinance (BIST, .IS) · TCMB EVDS (kur, enflasyon) · yerel önbellek
```

---

## 📁 Klasör yapısı

```
bist_asistan/
├── README.md
├── requirements.txt
├── .env.example            # API anahtarı şablonu (gerçek .env commit edilmez)
├── .gitignore
├── src/
│   ├── config.py           # hisse listesi, tarih aralıkları, komisyon oranı
│   ├── data/
│   │   ├── fetch.py        # yfinance + EVDS veri çekme
│   │   └── cache.py        # parquet ile yerel önbellek
│   ├── features/
│   │   └── indicators.py   # getiri, volatilite, RSI, MA, makro özellikler
│   ├── models/
│   │   ├── train.py        # walk-forward eğitim
│   │   ├── evaluate.py     # metrikler + baseline karşılaştırması
│   │   └── predict.py
│   ├── charting/
│   │   ├── chart.py        # mum grafiği, indikatör katmanları, çizim modları
│   │   └── drawings.py     # çizimleri JSON olarak kaydetme/yükleme
│   ├── backtest/
│   │   ├── engine.py       # vektörel backtest motoru (kendi yazdığımız)
│   │   ├── strategies.py   # al-ve-tut, MA kesişimi, RSI, ML sinyali
│   │   └── metrics.py      # toplam getiri, CAGR, Sharpe, max drawdown, win rate
│   └── agent/
│       ├── tools.py        # ajanın çağırabileceği araçlar
│       └── agent.py        # LLM ajan döngüsü
├── app/
│   └── streamlit_app.py
├── notebooks/
│   └── 01_kesif.ipynb      # keşifsel veri analizi
├── data/                   # parquet önbelleği ve çizim JSON'ları (git'e girmez)
├── tests/
└── docs/
    ├── mulakat-notlari.md  # her modül için "mülakatta nasıl anlatırım"
    └── deney-gunlugu.md    # ML iyileştirme deneyleri ve sonuçları
```

---

## 🧩 Modüller

### 1. Veri katmanı
- **Hisseler:** BIST 30'dan seçilmiş 10–15 likit hisse (ör. THYAO.IS, GARAN.IS, ASELS.IS, BIMAS.IS, KCHOL.IS, AKBNK.IS, EREGL.IS, SISE.IS, TUPRS.IS, FROTO.IS) ve XU100.IS endeksi
- **Makro veri:** USD/TRY (yfinance `TRY=X`), TÜFE ve politika faizi (TCMB EVDS, ücretsiz API anahtarı gerekir. Anahtar yoksa bu kısım atlanabilir olmalı.)
- Veriler `data/` klasöründe parquet olarak önbelleğe alınır, her seferinde yeniden indirilmez.
- Eksik gün, bölünme ve temettü düzeltmeleri kontrol edilir.

### 2. ML tahmin modülü
- **Hedef:** Önümüzdeki 5 işlem gününde getirinin pozitif olup olmayacağı (sınıflandırma). Alternatif: 20 günlük volatilite tahmini (regresyon). Volatilite tahmini genelde daha başarılı olur, ikisi de denenebilir.
- **Özellikler:** Gecikmeli getiriler, hareketli ortalamalar, RSI, volatilite, hacim değişimi, XU100 getirisi, USD/TRY değişimi
- **Modeller:** Önce Logistic Regression (baseline), sonra Random Forest / LightGBM
- **Değerlendirme kuralları (çok önemli):**
  - Zaman serisi olduğu için **rastgele bölme yok**. `TimeSeriesSplit` / walk-forward doğrulama kullanılır.
  - **Look-ahead bias** olmamalı. Hiçbir özellik geleceğe ait bilgi kullanamaz.
  - Model her zaman basit baseline'larla karşılaştırılır ("hep yükselir" tahmini, rastgele tahmin).
  - Sonuçlar dürüstçe raporlanır. %52–55 doğruluk finansta normaldir, abartılmaz.
- **İyileştirme deneyleri:** Model tek seferde bırakılmaz, adım adım geliştirilir. Her deney `docs/deney-gunlugu.md` dosyasına kaydedilir (ne değişti, sonuç ne oldu):
  - Yeni özellikler eklemek (makro veriler, sektör endeksi, hacim anomalileri)
  - Farklı hedefler denemek (5 gün yerine 20 gün, yön yerine volatilite)
  - Hiperparametre ayarı (sadece walk-forward doğrulama üzerinde)
  - Sadece model "emin" olduğunda sinyal üretmek (olasılık eşiği)
- **Aşırı öğrenme alarmı:** Doğruluk birden %65'in üstüne çıkarsa bu bir başarı değil, büyük ihtimalle veri sızıntısı veya aşırı öğrenme (overfitting) işaretidir. Böyle bir durumda sonuç kabul edilmeden önce kontrol edilir.
- **Asıl başarı ölçütü** doğruluk oranı değil, modelin sinyaliyle yapılan stratejinin komisyon dahil al-ve-tut'u geçip geçmediğidir.

### 3. Backtest motoru
- `pandas` ile **kendimiz yazıyoruz** (hazır kütüphane yerine). Böylece mülakatta her satırı açıklayabiliriz.
- **Stratejiler:** Al-ve-tut (karşılaştırma ölçütü), MA kesişimi, RSI, ML model sinyali
- **Gerçekçilik:** İşlem komisyonu (varsayılan %0,1, `config.py`'den ayarlanır), sinyal ertesi günün açılışında uygulanır.
- **Metrikler:** Toplam getiri, yıllık getiri (CAGR), Sharpe oranı, maksimum düşüş (max drawdown), işlem sayısı, kazanma oranı
- **TL ve USD bazlı getiri** ayrı gösterilir. Türkiye'de yüksek enflasyon nedeniyle bu önemli bir fark yaratır ve projeyi diğerlerinden ayırır.

### 4. LLM ajanı
- Claude API ile **tool use** (fonksiyon çağırma). Kullanılacak model ve SDK sürümü güncel Anthropic dokümantasyonuna göre seçilir.
- **Araçlar:**
  - `hisse_ozeti(sembol, donem)`: fiyat, getiri, volatilite özeti
  - `backtest_calistir(sembol, strateji, baslangic, bitis)`: backtest sonuçları
  - `model_tahmini(sembol)`: güncel tahmin, olasılık ve modelin geçmiş başarısı
  - `hisse_karsilastir(semboller, metrik)`
  - `makro_veri(gosterge, donem)`: kur, enflasyon
- **Kurallar (system prompt):** Türkçe cevap verir, sayıları araçlardan alır ve asla uydurmaz, her tahminde belirsizliği belirtir, yatırım tavsiyesi vermez.
- API anahtarı `.env` dosyasından okunur. Anahtar yoksa uygulama sohbet sekmesi hariç çalışmaya devam eder.

### 5. Ücretsiz grafik ve çizim aracı
Piyasadaki popüler grafik platformları, birkaç çizim ve indikatörden sonra ücretli üyelik istiyor. Bu modül, temel teknik analiz ihtiyacını **tamamen ücretsiz ve sınırsız** karşılayan basit bir alternatif.

- **Mum grafiği** (Plotly), hacim çubukları, zaman aralığı seçimi (günlük / haftalık / aylık)
- **Çizim araçları:** trend çizgisi, yatay destek/direnç çizgisi, dikdörtgen bölge, serbest çizim, silgi (Plotly'nin yerleşik çizim modları). **Çizim sayısında sınır yok.**
- **İndikatörler:** MA, EMA, RSI, MACD, Bollinger Bantları. Aynı anda istenildiği kadar eklenebilir.
- **Çizimleri kaydetme:** Kullanıcının çizimleri hisse bazında yerel bir JSON dosyasına kaydedilir ve hisse tekrar açıldığında geri yüklenir.
- **Ajan entegrasyonu:** Ajan, grafikteki indikatörleri yorumlayabilir. Örnek: *"Grafikte gördüğüm RSI 75, bu ne anlama geliyor?"*
- **Sınırlamalar (açıkça belirtilmeli):** Veri gecikmeli gelir (anlık değil), çizimler kullanıcı hesabına değil yerel dosyaya kaydedilir, otomatik formasyon tanıma yoktur.
- Başka bir platformun adı, logosu veya tasarımı kopyalanmaz. Kendi özgün arayüzümüz olur.

### 6. Streamlit arayüzü
- **Sekmeler:** Sohbet · Grafik (çizim araçlı) · Hisse Analizi · Backtest (strateji seçimi ve sermaye eğrisi) · Model Performansı
- Streamlit Community Cloud'a ücretsiz deploy edilir ve README'ye demo linki eklenir.

---

## 🗺️ Geliştirme planı

Her aşama bitince çalışır durumda olmalı ve ayrı commit'lenmeli.

- [x] **Aşama 0: Kurulum.** Klasör yapısı, `requirements.txt`, `.gitignore`, `.env.example`, git init
- [ ] **Aşama 1: Veri katmanı.** Veri çekme, önbellek ve testler. Keşif notebook'u.
- [ ] **Aşama 2: Özellikler ve ML.** Walk-forward eğitim, baseline karşılaştırması, sonuç raporu
- [ ] **Aşama 3: Backtest.** Motor, 4 strateji, metrikler, TL/USD karşılaştırması, testler
- [ ] **Aşama 4: Streamlit.** Analiz, Backtest ve Model sekmeleri (ajan olmadan)
- [ ] **Aşama 4b: Grafik aracı.** Mum grafiği, indikatörler, çizim araçları, çizimleri kaydetme
- [ ] **Aşama 5: LLM ajanı.** Araçlar, ajan döngüsü, Sohbet sekmesi
- [ ] **Aşama 6: Cila.** README'ye ekran görüntüleri ve sonuç tabloları, deploy, `docs/mulakat-notlari.md`

---

## 🤖 Claude Code için çalışma talimatları

Bu projeyi geliştiren kişi bir **YBS öğrencisi** ve projeyi staj mülakatlarında anlatacak. Bu yüzden:

1. **Aşama aşama ilerle.** Bir aşamayı bitirip çalıştığını göstermeden diğerine geçme. Her aşamanın sonunda ne yaptığını kısaca özetle.
2. **Önemli kararları bana sor.** Model seçimi, hedef değişken veya strateji gibi konularda seçenekleri artı ve eksileriyle sun, kararı ben vereyim.
3. **Her aşamanın sonunda** `docs/mulakat-notlari.md` dosyasına o modül için şunları ekle: ne yaptık, neden böyle yaptık, karşılaşılan sorunlar, olası mülakat soruları ve cevapları.
4. **Kod okunabilir olsun.** Fonksiyonlarda kısa Türkçe docstring olsun, gereksiz karmaşıklık olmasın.
5. **Finansal doğruluk:** Look-ahead bias, survivorship bias ve gerçekçi olmayan varsayımlara karşı dikkatli ol. Gördüğün riskleri açıkça belirt.
6. **Güvenlik:** API anahtarları asla koda veya git'e girmesin, sadece `.env` dosyasında olsun.
7. **Testler:** Backtest metrikleri ve özellik hesaplamaları için `pytest` testleri yaz.

---

## 🚀 Kurulum

```bash
git clone <repo-url>
cd bist_asistan
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # sonra .env içine kendi anahtarlarını yaz
streamlit run app/streamlit_app.py
```

**.env değişkenleri:**
```
ANTHROPIC_API_KEY=   # LLM ajanı için (opsiyonel)
EVDS_API_KEY=        # TCMB makro verisi için (opsiyonel)
```

---

## 📊 Sonuçlar

*(Aşama 6'da doldurulacak: model performans tablosu, strateji karşılaştırması, ekran görüntüleri ve demo linki.)*

---

## 🛠️ Teknolojiler

Python · pandas · numpy · scikit-learn · LightGBM · yfinance · evds · Plotly · Streamlit · Anthropic Claude API · pytest

---

*Bu proje AI destekli geliştirme araçları (Claude Code) kullanılarak geliştirilmiştir. Tüm tasarım kararları geliştirici tarafından verilmiş ve doğrulanmıştır.*
