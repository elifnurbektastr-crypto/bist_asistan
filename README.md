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
│   ├── depo.py             # duyurular ve geri bildirimler (SQLite → yayında Supabase)
│   ├── data/
│   │   ├── fetch.py        # yfinance + EVDS veri çekme, ham/düzeltilmiş fiyat
│   │   ├── cache.py        # parquet ile yerel önbellek
│   │   ├── quality.py      # veri kalitesi kontrolleri (eksik gün, limit aşımı, bölünme)
│   │   ├── dividends.py    # temettü geçmişi, özet, yaklaşanlar, filtreleme
│   │   └── guncelle.py     # tüm veriyi güncelleyen komut: python -m src.data.guncelle
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
│   ├── streamlit_app.py    # kullanıcı arayüzü (internette)
│   ├── ortak.py            # veri yükleme, grafik teması, duyuru, geri bildirim
│   ├── sekmeler/           # analiz.py, temettu.py, backtest.py, model.py
│   └── admin_app.py        # yönetici sayfası (sadece yerel bilgisayarda)
├── referans/
│   └── bist100.csv         # hisse evreni (kaynak ve tarih referans/README.md'de)
├── ileri_test/             # ileri test kayıtları (git'te, her gün otomatik commit)
│   ├── tahminler/          # günlük tahmin dosyaları (YYYY-AA-GG.csv), değiştirilemez
│   ├── acilislar/          # sabah kaydedilen açılış fiyatları (YYYY-AA-GG.csv)
│   ├── zincir.csv          # tahminlerin SHA-256 parmak izi zinciri
│   ├── acilis_zincir.csv   # açılış kayıtlarının parmak izi zinciri
│   ├── model_surumu.json   # dondurulmuş modelin parmak izi
│   └── ileri_test.xlsx     # korumalı Excel raporu (kayıtlardan üretilir, git dışında)
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
- **Hisseler:** Önce BIST 100 (`referans/bist100.csv`), ileride tüm BIST. XU100.IS endeksi karşılaştırma ölçütüdür. Fiyatlar 2015'ten itibaren.
- **Makro veri:** USD/TRY (yfinance `TRY=X`), TÜFE (`TP.TUKFIY2025.GENEL`, 2025=100) ve politika faizi (`TP.APIFON4`) TCMB EVDS'ten. Anahtar yoksa bu kısım atlanır.
- Veriler `data/` klasöründe parquet olarak önbelleğe alınır; sonraki çalıştırmalarda sadece eksik günler indirilir.
- **Ham + düzeltilmiş fiyat:** Grafikte o gün gerçekte işlem gören fiyat, getiri ve backtest hesaplarında bölünme + temettü düzeltilmiş fiyat kullanılır.
- **Kalite kontrolleri:** eksik gün, tatil satırları (Yahoo tatilleri önceki fiyatla dolduruyor, temizlenir), ±%10 limit aşımı, bölünme hesabının doğrulanması.
- **Bilinen sınırlamalar:**
  - Yahoo BIST verisini zaman zaman engelliyor; kod yeniden dener, olmazsa önbelleğe döner.
  - Bedelli sermaye artırımları Yahoo'da düzeltilmiyor, bu günlerde sahte düşüşler görülebilir.
  - Hisse listesi bugünkü BIST 100'dür (survivorship bias).
  - TÜFE ay bittikten sonra açıklanır; özelliklerde `tufe_yayin_tarihi` kullanılmalıdır (look-ahead).

### 1b. Temettü
- **Geçmiş:** Her ödeme hem o gün ödenen TL hem de bugünkü hisse sayısı bazında. Bedelsiz bölünmelerden sonra verimin doğru hesaplanması için bu ayrım gerekli.
- **Özet tablo:** son temettü tarihi ve tutarı, son 12 ay toplam TL ve verim, kesintisiz temettü yılı.
- **Yaklaşan temettüler:** yfinance'ten gelir, **doğrulanmamıştır** (resmi kaynak KAP); ekranda bu etiketle gösterilir.
- **Filtreleme:** minimum verim, minimum TL, önümüzdeki N gün içinde hak kullanımı, kesintisiz yıl, sektör.
- Tutarlar brüttür (stopaj düşülmemiştir).

### 2. ML tahmin modülü
- **Hedef:** Önümüzdeki 5 işlem gününde getirinin pozitif olup olmayacağı (sınıflandırma). Alternatif: 20 günlük volatilite tahmini (regresyon). Volatilite tahmini genelde daha başarılı olur, ikisi de denenebilir.
- **Özellikler:** Gecikmeli getiriler, hareketli ortalamalar, RSI, volatilite, hacim değişimi, XU100 getirisi, USD/TRY değişimi
- **Modeller:** Önce Logistic Regression (baseline), sonra Random Forest / LightGBM. Hiyerarşik yaklaşım: tüm hisselerden ortak model → benzer hisse grupları → hisseye göre ince ayar.
- **Özellik seçimi:** Piyasa geneli özellikler (endeks, kur, enflasyon, faiz) modeli piyasa zamanlamasına itip 2022 rejim değişiminde ters tahmine yol açtığı için varsayılan setten çıkarıldı (bkz. deney günlüğü, Deney 1-2).
- **Aşama 2 sonucu (2019-2026, walk-forward):** Yön modeli doğrulukta "hep yükselir" çıtasını (%54,4) geçemedi (%52,3, AUC 0,516). Model en emin olduğu %14'lük dilimde %57,9 isabet sağladı. Volatilite modeli her yıl basit çıtayı geçti (hata %21 daha düşük).
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

### 2b. İleri test (paper trading)
Backtest geçmişe bakar; ileri test ise modeli **gerçek zamanlı** sınar: tahmin yapıldığı anda gelecek gerçekten bilinmez.
- Her iş günü akşamı (Windows Görev Zamanlayıcı, 19:00 + yeniden denemeler) BIST 100 için tahmin üretilir.
- Her iş günü sabahı (10:30 + yeniden denemeler) 100 hissenin açılış fiyatı ayrı bir parmak izi zinciriyle kaydedilir; bu kayıt sadece o gün seans bitmeden yapılabilir.
- **Ara durum:** Her tahmin için girişten sonraki her günün kapanışına göre o ana kadarki getiri izlenir (1. gün … 5. gün); kesin sonuç 5. gün.
- **Dondurulmuş model:** İleri test boyunca model değişmez; parmak izi git'te, dosya değişirse tahmin üretilmez.
- **Değiştirilemezlik:** Günlük tahmin dosyaları SHA-256 parmak iziyle birbirine zincirlenir ve git'e commit'lenir. Tek bir sayı değişse `python -m src.ileri_test.gunluk --dogrula` hangi günde olduğunu söyler.
- **Süre kuralı:** Bir günün tahmini en geç ertesi seans açılışına (09:55) kadar yapılabilir; kaçırılan günler sonradan doldurulmaz.
- **Sonuçlar:** 5 iş günü dolunca gerçekleşen getiri hesaplanır ve walk-forward beklentisiyle karşılaştırılır.
- **Excel (`ileri_test/ileri_test.xlsx`, korumalı):** Özet · Tahminler · Gözlemler (sabah açılış / akşam kapanış) · Hisse Özeti · Hisse Kartı (genel bilgi) · Günlük · Bütünlük.

### 3. Backtest motoru
- `pandas` ile **kendimiz yazıyoruz** (hazır kütüphane yerine). Böylece mülakatta her satırı açıklayabiliriz.
- **Stratejiler:** Al-ve-tut (karşılaştırma ölçütü), MA kesişimi, RSI, ML model sinyali
- **Gerçekçilik:** İşlem komisyonu (varsayılan %0,1, `config.py`'den ayarlanır), sinyal ertesi günün açılışında uygulanır.
- **Metrikler:** Toplam getiri, yıllık getiri (CAGR), Sharpe oranı, maksimum düşüş (max drawdown), işlem sayısı, kazanma oranı
- **TL ve USD bazlı getiri** ayrı gösterilir. Türkiye'de yüksek enflasyon nedeniyle bu önemli bir fark yaratır ve projeyi diğerlerinden ayırır.
- **Türkiye'ye özgü gerçekçilik:** Piyasa dışındaki nakit politika faizi kazanır (para piyasası fonu varsayımı); Sharpe'ta risksiz faiz = politika faizi. İşlem maliyeti %0,1 komisyon + %0,05 kayma.
- **ML portföyü:** 5 günde bir, eşiği aşan en güçlü 10 hisse. Karşılaştırma: XU100, eşit ağırlıklı 81 hisse, rastgele 10 hisse.
- **Aşama 3 sonucu (2019-2026):** ML portföyü yıllık %35 (TL) ile eşit ağırlıklı portföyün (%56) ve rastgele seçimin (%38) gerisinde kaldı; maliyetsiz senaryoda da geride. Model sinyali al-ve-tut'u geçmiyor. Ayrıntılar: `docs/deney-gunlugu.md`.

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
- **Sekmeler:** Sohbet · Grafik (çizim araçlı) · Hisse Analizi · Temettü · Backtest (strateji seçimi ve sermaye eğrisi) · Model Performansı
- Kullanıcılar kısa geri bildirim bırakabilir (👍/👎 ve en fazla 200 karakter not), yöneticinin duyuruları sayfanın üstünde görünür.
- **Güncel model sinyalleri herkese açık sayfada gösterilmez** (yatırım tavsiyesi algısı / SPK düzenlemesi); sadece modelin geçmiş ve ileri test performansı gösterilir. Güncel tahminler yalnızca yerel admin sayfasında.
- Uygulama internete gitmez: veriyi yerel taraf günceller, uygulama önbellekten okur (Yahoo bulut sunucularını daha sık engelliyor).
- Streamlit Community Cloud'a ücretsiz deploy edilir ve README'ye demo linki eklenir.

### 7. Yönetici (admin) sayfası
- **Sadece yerel bilgisayarda çalışır, internete açılmaz**; bu yüzden şifre gerekmez.
- Elle veri girişi/düzeltme, duyuru yayınlama, kullanıcı geri bildirimlerini okuma, veri güncelleme ve kalite raporu.
- Kullanıcı sayfası ile ortak veri deposu (duyurular ve geri bildirimler için) Aşama 4'te seçilecek.

---

## 🗺️ Geliştirme planı

Her aşama bitince çalışır durumda olmalı ve ayrı commit'lenmeli.

- [x] **Aşama 0: Kurulum.** Klasör yapısı, `requirements.txt`, `.gitignore`, `.env.example`, git init
- [x] **Aşama 1: Veri katmanı.** Veri çekme, önbellek ve testler. Keşif notebook'u.
- [x] **Aşama 2: Özellikler ve ML.** Walk-forward eğitim, baseline karşılaştırması, sonuç raporu
- [x] **Aşama 3a: İleri test.** Dondurulmuş model, günlük tahmin, parmak izi zinciri, korumalı Excel, Görev Zamanlayıcı
- [x] **Aşama 3: Backtest.** Motor, 4 strateji, metrikler, TL/USD karşılaştırması, testler
- [x] **Aşama 4: Streamlit.** Analiz, Temettü, Backtest ve Model sekmeleri (ajan olmadan), geri bildirim
- [ ] **Aşama 4a: Admin sayfası.** Elle veri girişi, duyurular, geri bildirimler, veri güncelleme (yerel)
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

Python · pandas · numpy · pyarrow · scikit-learn · LightGBM · yfinance · evds · Plotly · Streamlit · Anthropic Claude API · pytest

---

*Bu proje AI destekli geliştirme araçları (Claude Code) kullanılarak geliştirilmiştir. Tüm tasarım kararları geliştirici tarafından verilmiş ve doğrulanmıştır.*
