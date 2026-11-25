# 🎤 Mülakat Notları

Her aşama için: **ne yaptık, neden böyle yaptık, karşılaşılan sorunlar, olası mülakat soruları ve cevapları.**

---

## Aşama 0: Kurulum

### Ne yaptık?
- Modüler bir klasör yapısı kurduk: `src/` altında veri, özellikler, modeller, grafik, backtest ve ajan ayrı paketler hâlinde duruyor. Arayüz (`app/`), testler (`tests/`) ve dokümanlar (`docs/`) ayrı tutuluyor.
- `requirements.txt` (alt sürüm sınırlarıyla) ve `requirements-lock.txt` (`pip freeze` ile birebir sürümler) dosyalarını hazırladık.
- `.gitignore` ve `.env.example` dosyalarını oluşturduk. API anahtarları yalnızca `.env` dosyasında duruyor ve bu dosya git'e girmiyor.
- Python 3.12 ile `.venv` sanal ortamını kurduk ve git deposunu başlattık.

### Neden böyle yaptık?
- **Modüler yapı:** Her katmanın tek bir sorumluluğu var. Örneğin backtest motoru, verinin yfinance'ten mi yoksa önbellekten mi geldiğini bilmek zorunda değil. Bu sayede hem test etmek hem de ajana "araç" olarak bağlamak kolaylaşıyor.
- **Sanal ortam:** Proje bağımlılıkları bilgisayardaki diğer projelerle çakışmıyor.
- **İki ayrı requirements dosyası:** `requirements.txt` esnek kalıyor (yeni güvenlik yamaları gelebilir). `requirements-lock.txt` ise "bende çalışıyordu" sorununu önlüyor, aynı ortamı birebir yeniden kurmayı sağlıyor.
- **`.env` ve `.env.example`:** Gizli anahtarlar koddan ayrı tutuluyor. Şablon dosya, projeyi klonlayan kişiye hangi değişkenlerin gerektiğini gösteriyor.
- **`data/` git dışında:** Veri yeniden indirilebilir ve büyük. Ayrıca veri sağlayıcının verisini herkese açık bir repoda yeniden dağıtmak da istemiyoruz.
- **Python 3.12:** 3.13'e göre bilimsel kütüphanelerde (LightGBM vb.) daha olgun ve sorunsuz bir destek sunuyor.

### Karşılaşılan sorunlar
- Proje başta **OneDrive** klasöründeydi. Sanal ortam on binlerce dosya içerdiği için senkronizasyon yavaşlığı ve `.git`/`.venv` dosyalarında kilitlenme riski vardı. Projeyi `C:\Users\<kullanıcı>\projeler\bist_asistan` konumuna taşıdık. Yedekleme görevini git ve GitHub üstlenecek.

### Olası mülakat soruları
**S: API anahtarlarını nasıl yönetiyorsun?**
C: Anahtarlar `.env` dosyasında duruyor ve `python-dotenv` ile okunuyor. `.env` dosyası `.gitignore` içinde olduğu için git'e hiç girmiyor. Repoda yalnızca boş bir şablon olan `.env.example` var. Deploy ortamında da platformun "secrets" yönetimini kullanacağım.

**S: Neden Docker değil de venv?**
C: Bu ölçekte bir tek kişilik proje ve Streamlit Community Cloud'a deploy için venv ile `requirements.txt` yeterli. Proje birden fazla servise ayrılırsa Docker mantıklı bir sonraki adım olur.

**S: Projeyi başka biri nasıl çalıştırır?**
C: Repoyu klonlar, sanal ortamı kurar, `pip install -r requirements.txt` komutunu çalıştırır, `.env.example` dosyasını `.env` olarak kopyalar (anahtarlar opsiyonel) ve `streamlit run` ile uygulamayı başlatır. Adımlar README'de yazılı.

---

## Aşama 1: Veri katmanı

### Ne yaptık?
- **Evren:** BIST 100 (100 hisse, `referans/bist100.csv`), XU100 endeksi, USD/TRY kuru; 2015'ten bugüne günlük veri.
- **Makro:** TCMB EVDS'ten TÜFE (2025=100 bazlı yeni seri) ve politika faizi (AOFM).
- **Önbellek:** Parquet dosyaları; sonraki çalıştırmalarda sadece son ~10 gün yeniden indiriliyor (artımlı güncelleme). Yeni bir temettü/bölünme gelirse geçmişin tamamı yeniden indiriliyor, çünkü düzeltme katsayıları değişiyor.
- **Ham + düzeltilmiş fiyat:** Ham fiyat grafikte gösteriliyor, düzeltilmiş fiyat (bölünme + temettü) getiri hesaplarında kullanılıyor.
- **Temettü modülü:** Her ödeme hem o gün ödenen TL hem de bugünkü hisse bazında. Son 12 ay verimi, kesintisiz yıl, yaklaşan hak kullanım tarihleri (yfinance, doğrulanmamış) ve filtreleme.
- **Kalite kontrolleri:** eksik gün, tatil satırları, OHLC tutarlılığı, limit aşımı, şüpheli sıçrama (>%35), bölünme hesabının doğrulanması.
- **Elle düzeltme:** `referans/duzeltmeler.csv` dosyası ile Yahoo'nun kaçırdığı sermaye artırımları düzeltiliyor.
- **Testler:** 33 pytest testi, internete bağlanmadan sahte veriyle çalışıyor.
- **Keşif notebook'u:** `notebooks/01_kesif.ipynb`.

### Neden böyle yaptık?
- **Ham ve düzeltilmiş fiyatı ayrı tutmak:** FROTO 2025'te 1:10 bedelsiz yaptı. Ham fiyat o gün %90 "düşüyor", ama yatırımcının serveti değişmiyor. Getiri ham fiyattan hesaplansa sahte bir -%90 oluşur; grafik düzeltilmiş fiyatla çizilse kullanıcı ekranda aracı kurumundaki fiyatı görmez.
- **Temettüyü iki bazda tutmak:** Verim hesabında bölünme öncesi temettüyü bugünkü fiyata bölersek verim olduğundan yüksek çıkar. Bu yüzden payda ile pay aynı hisse bazında olmalı.
- **Önce önbellek:** Yahoo istekleri sınırlıyor. 100 hisseyi her açılışta indirmek hem yavaş hem de engellenme sebebi.
- **Devre kesici:** Üst üste 3 hisse gelmezse Yahoo engelliyor demektir; dakikalarca beklemek yerine durup önbelleğe dönüyoruz.
- **Seans bitmeden bugünün çubuğunu atmak:** Seans içindeki fiyat kesinleşmemiştir; backtest'te kullanılırsa geleceği görmek (look-ahead bias) olur.
- **TÜFE yayın tarihi:** Ekim enflasyonu 3 Kasım'da açıklanır. Model Ekim verisini Ekim ayı içinde "görürse" bu bir sızıntıdır. Bu yüzden `tufe_yayin_tarihi` sütununu ekledik.

### Karşılaşılan sorunlar (mülakatta en çok anlatılacak kısım)
1. **Yahoo istek sınırlaması:** Aynı sembol bir dakika gelip bir sonraki dakika "possibly delisted" diyerek boş döndü. Çözüm: yeniden deneme, ikinci tur, devre kesici ve önbellek. XU100 endeksi gün içinde hiç gelmedi; sistem önbellekle çalışmaya devam ediyor.
2. **Sessiz veri kaybı:** Toplu indirme (`yf.download`) temettü ve bölünme sütunlarını hiç döndürmüyordu; kod bunları sıfırla doldurup hiç hata vermeden yanlış fiyat üretecekti. Tek tek indirmeye geçtik.
3. **Tatil günleri:** Yahoo resmi tatilleri önceki fiyatla doldurmuş (her hissede ~48 sahte gün). Bu günler volatiliteyi düşük gösterir ve "5 işlem günü sonrası" hedefini kaydırır. Hacmi sıfır olan günleri temizledik.
4. **Yahoo'nun kaçırdığı sermaye artırımları:** CCOLA'da bir günde -%91, FENER'de üç kez -%60/-%79. Bunlar büyük ihtimalle Yahoo'nun kaydetmediği bedelsiz ya da bedelli/bedelsiz artırımlar (CCOLA'daki oran 1:10'a çok yakın). %35 üstü sıçramaları otomatik tespit edip `duzeltmeler.csv` ile düzelttik. Basıklık 373'ten 9'a indi. Oranlar şimdilik fiyattan tahmin, KAP'tan doğrulanacak.
5. **EVDS tuzakları:** (a) Paket bitiş tarihi verilmezse sadece tek gün döndürüyordu. (b) API tek istekte ~1000 satırdan fazlasını vermiyor; istekleri 3 yıllık parçalara böldük. (c) TÜİK 2026'da baz yılını değiştirdi ve eski TÜFE serisi kesildi; yeni seriye geçtik.

### Bilinen sınırlamalar
- Hisse listesi bugünkü BIST 100 → **survivorship bias** (arada endeksten çıkan ya da kapanan şirketler yok).
- Liste resmi Borsa İstanbul dosyası değil, Midas tablosundan alındı.
- Yaklaşan temettü tarihleri doğrulanmamış (resmi kaynak KAP).
- 10 sermaye artırımı düzeltmesi tahmini oranla yapıldı.
- 19 hissenin geçmişi 5 yıldan kısa (yeni halka arzlar).

### Olası mülakat soruları
**S: Bölünme düzeltmesinin doğru olduğundan nasıl emin oldun?**
C: Test ettim. Bölünme günü ham fiyat oran kadar düşmeli, düzeltilmiş fiyat düşmemeli. Yani (ham sıçrama / düzeltilmiş sıçrama) oranı bölünme oranına eşit olmalı. BIST 100'deki 99 bölünmenin hepsinde bu oran 1,000 çıktı. Ayrıca sahte veriyle hem doğru hem de yanlış senaryoyu test eden pytest testleri var.

**S: Veri kaynağın güvenilir mi?**
C: Tamamen değil, ve bunu ölçtüm. Yahoo bazı sermaye artırımlarını kaçırıyor, tatilleri sahte günlerle dolduruyor ve istekleri sınırlıyor. Her birini tespit eden bir kontrol yazdım ve sınırlamaları dokümante ettim. Gerçek bir üründe lisanslı bir veri sağlayıcı (ör. Borsa İstanbul'un veri dağıtımı) kullanılmalı.

**S: Look-ahead bias'ı veri katmanında nasıl önledin?**
C: Üç yerde. Seans bitmeden alınan bugünkü fiyatı atıyorum. TÜFE'yi yayınlandığı tarihe göre kullanmak için yayın tarihini saklıyorum. Ve hisse listesindeki survivorship bias'ı açıkça belirtiyorum.

**S: Neden temettü verimini kendin hesapladın, yfinance'in verdiğini kullanmadın?**
C: yfinance'in hazır alanları tutarsızdı: FROTO yıllık temettüsü 0 görünüyordu, verim bazen yüzde bazen oran olarak geliyordu. Ham ödeme geçmişinden kendim hesaplayınca hem tutarlı hem de açıklanabilir oluyor.

**S: Bir hata ile gerçek bir piyasa olayını nasıl ayırdın?**
C: Aynı gün kaç hissenin etkilendiğine baktım. 15 Şubat 2023'te 81 hisse limiti aştı: bu deprem sonrası açılış, yani piyasa geneli bir olay. Tek bir hissede görülen %60-90'lık hareket ise kurumsal işlemdir. Ayrıca BIST'te normal işlemle tek günde %35'lik bir hareket neredeyse imkânsız; en uç gerçek olay olan deprem sonrası açılışta bile hareketler %22 civarında kaldı.

---

## Aşama 2: Özellikler ve ML

### Ne yaptık?
- **Özellikler (`src/features/indicators.py`):** 14 hisseye özgü özellik (geçmiş getiriler, volatilite, hareketli ortalama uzaklıkları, RSI, TL hacim oranı, gün içi aralık, endekse göre göreli getiri) ve 7 piyasa geneli özellik (endeks, kur, enflasyon, faiz). Hepsi oran cinsinden, böylece farklı fiyattaki hisseler tek modelde birlikte kullanılabiliyor.
- **Hedefler:** (1) yarının açılışında alıp 5 gün sonraki açılışta satınca TL getirisi pozitif mi? (2) önümüzdeki 20 günün volatilitesi.
- **Walk-forward (`src/models/train.py`):** 2019-2026 her yıl için ayrı eğitim; purging ile.
- **Modeller:** 2 baseline, lojistik regresyon, random forest, LightGBM ve hiyerarşik yaklaşım (benzer hisse grupları + hisseye göre ince ayar).
- **Değerlendirme (`src/models/evaluate.py`):** doğruluk, AUC, log-loss, eşik analizi, en iyi/en kötü %20 getiri farkı, aşırı öğrenme alarmı.
- **Güncel tahmin (`src/models/predict.py`):** son günün tahmini, sinyal gücü, beklenen volatilite ve modelin o hissedeki geçmiş başarısı.
- 5 deney `docs/deney-gunlugu.md` dosyasında. Toplam 53 test.

### Neden böyle yaptık?
- **Hedef yarının açılışından:** Sinyal akşam kapanışta üretiliyor, işlem ancak ertesi sabah yapılabilir. Kapanıştan kapanışa hedef, gerçekte yapılamayacak bir işlemi ölçerdi.
- **Purging:** 5 günlük hedef 6 gün ileri bakar. Eğitimin son günlerinin etiketleri test yılının fiyatlarını içerir; bu satırlar atılmazsa model sınav sorularını önceden görmüş olur. Bunu doğrulayan bir test var.
- **Çıta "hep yükselir":** TL'de enflasyon yüzünden hisseler 5 günlük dönemlerin %54'ünde yükseliyor. %52 doğruluk "%50'nin üstü" gibi görünse de aslında hiçbir şey yapmamaktan kötü.
- **Tek ortak model ve üzerine ince ayar:** Her hisseye ayrı model kurulsa her biri sadece ~2.900 örnekle eğitilirdi. Ortak model 200 bin örnekten genel kalıpları öğreniyor, ince ayar hisseye özgü sapmaları ekliyor.
- **Korelasyon grupları sadece eğitim verisinden:** Gruplar test dönemi verisiyle hesaplansaydı, geleceğe ait bilgi gruplama yoluyla modele sızardı.
- **Hiperparametreler sabit:** Test sonuçlarına bakıp ayar yapmak, test kümesini dolaylı yoldan eğitim verisine çevirir.

### Karşılaşılan sorunlar
1. **İlk sonuç yazı-turadan kötüydü (AUC 0,476).** Özellik önemlerine baktım: en önemli 7 özelliğin 7'si piyasa geneli özellikti (reel faiz, faiz, kur, endeks, enflasyon). Model hangi hissenin iyi olacağını değil, bütün borsanın ne yapacağını tahmin etmeye çalışıyordu. Bunu da eski rejimlerden öğrendiği için 2022'deki %80 enflasyon ortamında tersine döndü (o yıl doğruluk %38). Piyasa geneli özellikleri çıkarınca AUC 0,516'ya yükseldi ve 2022 doğruluğu %56 oldu.
2. **Hiyerarşik yaklaşım beklenen kazancı getirmedi.** Farklar 0,3 puanın altında kaldı. Bunu saklamak yerine deney günlüğüne yazdım.
3. **Yön tahmini zayıf, volatilite tahmini güçlü.** Bu finans literatürüyle uyumlu: getirinin yönü neredeyse rastgeledir, ama volatilite kümelenir (oynak dönemler oynak dönemleri izler).

### Olası mülakat soruları
**S: Modelin doğruluğu %52. Bu başarılı mı?**
C: Doğruluk olarak hayır; "hep yükselir" tahmini %54,4 yapıyor ve bunu açıkça raporluyorum. Ama iki yerde değer var. Model en emin olduğu %14'lük dilimde %58 isabet ve ortalamanın 0,42 puan üstünde 5 günlük getiri yakalıyor; bunun komisyondan sonra işe yarayıp yaramadığını backtest'te ölçüyorum. Volatilite tahmininde ise model basit yöntemi her yıl geçiyor ve hatayı %21 azaltıyor.

**S: Neden rastgele train/test bölmesi yapmadın?**
C: Zaman serisinde rastgele bölme, modelin 2023'ü bilerek 2021'i tahmin etmesine izin verir. Gerçekte gelecek bilinmez. Walk-forward her yıl sadece o güne kadarki veriyle eğitiyor. Buna ek olarak hedefin test dönemine taşan eğitim satırlarını da atıyorum (purging).

**S: Veri sızıntısını nasıl kontrol ettin?**
C: Üç yoldan. Birincisi, testlerden biri gelecekteki fiyatları 5 katına çıkarıp geçmiş özelliklerin değişmediğini doğruluyor. İkincisi, TÜFE'yi açıklandığı tarihten itibaren kullanıyorum. Üçüncüsü, doğruluk %65'i aşarsa alarm veren bir kontrol var. Bir de sağduyu kontrolü: rastgele yürüyüş verisinde model %50 civarında kalmalı, bu da test ediliyor.

**S: Özellik seçimini test sonucuna bakarak yaptın. Bu da bir tür sızıntı değil mi?**
C: Haklı bir soru, kısmen evet. Bu yüzden kararı sadece sonuca göre değil, mekanizmaya göre verdim: piyasa geneli özelliklerin rejim değişiminde neden bozulduğunu özellik önemleriyle gösterdim. Daha temiz yöntem, 2025-2026'yı hiç dokunulmamış son test olarak ayırmak olurdu. Bunu bir sonraki iyileştirme olarak not ettim.

**S: LightGBM'de ince ayar nasıl çalışıyor?**
C: Ortak model 300 ağaçla bütün hisselerden eğitiliyor. Sonra her hisse için LightGBM'in `init_model` parametresiyle o modelin üzerine, sadece o hissenin verisiyle ve düşük öğrenme oranıyla 40 ağaç daha ekleniyor. Yani model sıfırdan değil, ortak modelin bıraktığı hatalardan devam ediyor. Bu, derin öğrenmedeki transfer learning fikrinin ağaç modellerindeki karşılığı.
