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

---

## Aşama 3a: İleri test (paper trading)

### Ne yaptık?
- Model bir kez eğitilip **donduruldu** (v1, eğitim sonu 2026-11-16). Model dosyasının parmak izi git'te; dosya değişirse sistem tahmin üretmeyi reddediyor.
- Her iş günü akşamı BIST 100 için tahmin üretiliyor: yükseliş olasılığı, sinyal (güçlü al / zayıf al / al değil), beklenen 20 günlük volatilite, o günkü kapanış fiyatı.
- Her günün dosyası SHA-256 ile parmak izi alınıp bir önceki güne **zincirleniyor** ve otomatik olarak git'e commit'leniyor.
- 5 iş günü dolunca gerçekleşen getiri hesaplanıyor; model isabeti, "hep yükselir" çıtası ve walk-forward beklentisi yan yana raporlanıyor.
- Korumalı bir Excel raporu üretiliyor; içinde hisse bazında özet ve her hisse için bilgi kartı var.
- Windows Görev Zamanlayıcı her iş günü 19:00'da çalıştırıyor; 20:30, 22:30 ve ertesi sabah 08:30'da yeniden deniyor.

### Neden böyle yaptık?
- **Backtest yetmez:** Ne kadar dikkat edilse de backtest'te araştırmacı geçmişi bilir. Bu bilgi özellik seçimine, eşik seçimine ve model seçimine sızar (Aşama 2'de özellik setini test sonuçlarına bakarak değiştirdik). İleri testte gelecek gerçekten bilinmez.
- **Model dondurma:** Model ileri test sırasında değişseydi, sonuç birkaç modelin karışımını ölçerdi. Parmak izi de modelin gizlice değiştirilmediğini kanıtlıyor.
- **Parmak izi zinciri:** Excel'in koruması birkaç tıkla kaldırılabilir. Zincirde ise geçmişteki tek bir rakamı değiştirmek o günden sonraki bütün zincir değerlerini bozar. Değiştiren kişi zinciri baştan yeniden hesaplasa bile git geçmişindeki commit'lerle uyuşmaz. Banka denetim kayıtları (audit log) ve blokzincir aynı fikre dayanır.
- **Süre kuralı (ertesi seans 09:55):** Seans açıldıktan sonra yapılan "dünün tahmini" açılış fiyatını görmüş olabilir. Bu yüzden kaçırılan günler sonradan doldurulmuyor, kayıt dışı kalıyor.
- **Excel bir görünüm, kayıt değil:** Asıl kayıt CSV dosyaları ve zincir. Excel her gün bunlardan yeniden üretiliyor; Excel'deki bir değişiklik kayda yansımıyor.

### Karşılaşılan sorunlar
1. **Önbellek zamanlaması:** Önbellek "bugün güncellendiyse tekrar indirme" kuralıyla çalışıyordu. Gün içinde (ör. 15:00) yapılan bir okuma, akşamki görevin o günün kapanışını hiç indirmemesine yol açacaktı. Kural seans kapanışına göre düzeltildi ve testi yazıldı.
2. **Yahoo kesintileri:** Görev aynı akşam birden çok kez tetikleniyor. Aynı gün tekrar çalıştığında hiçbir şey yapmıyor, böylece ilk deneme başarısız olsa bile sonraki deneme kaydı tamamlıyor. Hisselerin %90'ından azı güncelse ya da endeks gelmediyse tahmin üretmiyor.
3. **Model boyutu:** 81 hisseye özel model ortak modelin ağaçlarını da içerdiği için dosya 22 MB oldu. Git'e sadece parmak izi giriyor.

### Sonradan eklenenler (kullanıcı geri bildirimiyle)
- **Sabah açılış kaydı:** Her iş günü 10:30'da 100 hissenin açılış fiyatı ayrı bir parmak izi zincirine yazılıyor. Bu kayıt sadece o gün ve seans bitmeden yapılabiliyor. Akşam gelen resmi açılışla %0,5'ten fazla fark varsa "Gözlemler" sayfasında işaretleniyor.
- **Günlük ara durum:** Model 5 günlük getiriyi tahmin ediyor, ama her akşam her tahmin için "bugüne kadar ne oldu" gösteriliyor (1. gün, 2. gün … 5. gün). Kesin hüküm 5. gün veriliyor. Modeli ertesi günün hareketiyle değerlendirmek, ona sorulmamış bir sorunun cevabını aramak olurdu.

### Olası mülakat soruları
**S: Backtest ile ileri test arasındaki fark ne?**
C: Backtest geçmiş veride stratejiyi simüle eder; araştırmacı sonucu bildiği için kararlarına bilmeden geçmiş bilgi sızabilir. İleri test modeli dondurup gerçek zamanlı tahmin ettirir. Tahmin yapıldığı anda gelecek bilinmediği için sızıntı imkânsızdır. Kurumsal tarafta bir strateji genellikle backtest ve ardından birkaç ay paper trading'den geçmeden gerçek parayla çalıştırılmaz.

**S: Sonuçları sonradan değiştirmediğini nasıl kanıtlarsın?**
C: Her günün tahmin dosyasının SHA-256 parmak izi bir önceki günün zincir değeriyle birleştirilip tekrar parmak izi alınıyor ve her gün git'e commit'leniyor. Doğrulama komutu zinciri baştan hesaplıyor. Geçmişte tek bir rakam değişse o gün "değiştirilmiş" olarak işaretleniyor. Zincir baştan yeniden hesaplansa bile git'teki tarihli commit'lerle uyuşmaz. Daha da güçlü bir kanıt için zincirin son değeri herkese açık bir yere (ör. GitHub) itilebilir.

**S: İleri test ne kadar sürmeli?**
C: İstatistiksel olarak yeterli tamamlanmış tahmin birikmeli. Günde 100 hisse ile bir ayda yaklaşık 2.000 tahmin oluşur. Ama aynı günün tahminleri birbirine bağımlıdır (hepsi aynı piyasa hareketini yaşar), bu yüzden asıl önemli olan gün sayısı. En az 3 ay ve farklı piyasa koşulları görmek gerekir. Sonuç walk-forward beklentisinden (%52,3 isabet, güçlü sinyalde %57,9) belirgin şekilde sapıyorsa bu, modelin piyasa koşulları değiştiği için artık işe yaramadığına (model drift) işaret eder.


---

## Aşama 3: Backtest

### Ne yaptık?
- **Kendi yazdığımız vektörel motor (`src/backtest/engine.py`):** Sinyal t kapanışında üretiliyor, pozisyon t+1 açılışında alınıyor, getiriler açılıştan açılışa hesaplanıyor. Her pozisyon değişiminde %0,1 komisyon + %0,05 kayma düşülüyor.
- **4 strateji (`strategies.py`):** Al-ve-tut, MA 20/50 kesişimi, RSI 30/70, ML sinyali (5 günde bir karar, 5 gün tutma).
- **ML portföyü:** Her 5 iş gününde bir, eşiği aşan en yüksek olasılıklı 10 hisse alınıyor; eşiği aşan hisse azsa kalan pay nakitte bekliyor. Volatiliteye göre ağırlıklandırılmış bir versiyonu da var.
- **Karşılaştırma ölçütleri:** XU100, 81 hissenin eşit ağırlıklı portföyü, rastgele 10 hisse (20 tekrar ortalaması).
- **Metrikler (`metrics.py`):** Toplam getiri, CAGR (TL ve USD), volatilite, Sharpe (risksiz faiz = politika faizi), maksimum düşüş (TL ve USD), işlem sayısı, kazanma oranı, piyasada kalma süresi.
- Nakitli ve nakitsiz senaryolar, maliyet duyarlılığı ve yıllık getiri tabloları.

### Sonuç (2019-2026)
- **ML stratejisi al-ve-tut'u geçemedi.** ML ilk 10 portföyü yıllık %35; aynı hisselerin eşit ağırlıklı portföyü %56, rastgele 10 hisse %38.
- Maliyet sıfır olsa bile ML geride kalıyor: sorun sadece komisyon değil, sinyalin kendisi zayıf.
- Hisse bazında MA kesişimi al-ve-tut'a yakın getiriyi daha düşük düşüşle (-%40'a karşı -%52) sağlıyor, ama hisselerin sadece yarısında geçiyor.
- USD bazında tablo çok farklı: XU100 yıllık sadece %4, ML %1,5. TL'deki yüksek getirilerin çoğu enflasyon ve kur kaybı.

### Neden böyle yaptık?
- **Açılıştan açılışa getiri:** Akşam üretilen sinyalle en erken ertesi sabah işlem yapılabilir. Kapanış fiyatından işlem varsaymak, gerçekte ulaşılamayacak bir fiyatı kullanmak olurdu.
- **Sharpe'ta politika faizi:** Faiz %36-50 iken risksiz faizi 0 saymak, enflasyonla şişmiş TL getirilerini olduğundan çok daha iyi gösterir.
- **Nakit faizi:** Türkiye'de piyasa dışındaki para, para piyasası fonunda yüksek faiz kazanır. Bunu hesaba katmamak seçici stratejilere haksızlık olur. Hesaba katmak ise getirinin nereden geldiğini gösterdi: ML 0,60 portföyünün getirisinin önemli kısmı faizden geliyordu.
- **Rastgele portföy karşılaştırması:** Bir modelin değeri, aynı kurallarla rastgele seçime göre ölçülmeli. Bu karşılaştırma modelin aslında bir avantajı olmadığını açıkça gösterdi.

### Karşılaşılan sorunlar ve dersler
1. **Havuzlanmış metrik tuzağı:** Aşama 2'de "model en emin olduğunda ortalamanın 0,42 puan üstünde getiri" bulmuştuk. Backtest bunu doğrulamadı, çünkü o metrik farklı günlerin hisselerini bir havuzda karşılaştırıyordu; fark büyük ölçüde piyasanın genel yükseldiği günlerden geliyordu. Portföy ise aynı gün içinde hisseleri sıralıyor. Ders: değerlendirme metriği, stratejinin gerçekte yapacağı işle aynı soruyu sormalı.
2. **Survivorship bias'ın görünür etkisi:** Eşit ağırlıklı 81 hisse XU100'ü yılda 17 puan geçiyor. Bunun büyük kısmı, hisse listesinin bugünün BIST 100'ünden (yani hayatta kalanlardan) seçilmesinden geliyor. Bu yüzden XU100 ile değil, aynı evrenden seçen eşit ağırlıklı portföyle karşılaştırma yapıyorum.

### Olası mülakat soruları
**S: Modelin para kazandırmıyor. Proje başarısız mı?**
C: Hayır. Projenin amacı para kazandıran bir model iddia etmek değil, bir fikri doğru test etmekti. Sızıntısız walk-forward, gerçekçi maliyet, rastgele portföy kıyası ve ileri test ile modelin avantajı olmadığını güvenilir şekilde gösterdim. Finansta en sık yapılan hata, kötü test edilmiş bir stratejiye güvenmek; bu proje o hatayı yapmamayı gösteriyor. Bir de olumlu sonuç var: volatilite modeli her yıl basit yöntemi geçiyor.

**S: Backtest'te en sık yapılan hatalar neler, sen nasıl önledin?**
C: (1) Look-ahead: sinyal kapanışta, işlem ertesi açılışta; bunu test eden bir pytest var. (2) Maliyetleri yok saymak: komisyon + kayma ve duyarlılık tablosu. (3) Survivorship bias: farkındayım ve karşılaştırmayı aynı evrende yapıyorum. (4) Aşırı optimizasyon: parametreleri test sonucuna göre ayarlamadım, 0,60 eşiğinin bu riski taşıdığını da raporladım. (5) Uygun olmayan ölçüt: rastgele portföy ve eşit ağırlık gibi adil karşılaştırmalar kullandım.

**S: Sharpe oranın neden bu kadar düşük?**
C: Çünkü risksiz faiz olarak %36-50 seviyesindeki politika faizini kullanıyorum. TL'de yıllık %35 getiri kulağa yüksek gelir, ama aynı dönemde mevduat da yaklaşık o kadar kazandırdı. Doğru soru "hisse almak faizden ne kadar fazla kazandırdı?" sorusu.

**S: Bundan sonra ne denerdin?**
C: Modeli doğrudan gün içi sıralama için eğitmek (hedef: o gün hisselerin ortancasını geçer mi). Değerlendirmeyi portföyün yaptığı işe uygun metrikle (günlük sıralama korelasyonu) yapmak. Devir hızını düşürmek (ör. sadece sinyal belirgin değiştiğinde işlem yapmak). Ve volatilite modelini risk yönetiminde kullanmak.

---

## Aşama 4: Streamlit arayüzü

### Ne yaptık?
- **Sekmeler:** Hisse Analizi (fiyat, TL/USD/XU100 getirisi, volatilite, maks. düşüş, RSI), Temettü (filtreler, en yüksek verimliler grafiği, hisse bazında ödeme geçmişi ve "elimdeki adet için ne kadar"), Backtest (tek hisse için canlı strateji karşılaştırması, TL/USD, maliyet ve nakit faizi ayarı; model portföyü sonuçları), Model Performansı (walk-forward, ileri test, deney günlüğü). Sohbet ve Grafik sekmeleri Aşama 5 ve 4b'de dolacak.
- **Duyurular ve geri bildirim:** Her sekmenin altında 👍/👎 ve en fazla 200 karakter not. Duyurular ve geri bildirimler `src/depo.py` arayüzü üzerinden SQLite'a yazılıyor; yayında aynı arayüzle Supabase'e geçilecek.
- **Testler:** Depo testleri (SQL enjeksiyonu dahil) ve Streamlit `AppTest` ile tüm uygulamanın hatasız açıldığını doğrulayan duman testi.

### Neden böyle yaptık?
- **Güncel sinyalleri herkese açık göstermemek:** Türkiye'de lisanssız yatırım danışmanlığı SPK düzenlemesine tabi; "güçlü al" gibi bir ifade tavsiye olarak algılanabilir. Ayrıca backtest modelin avantajı olmadığını gösterdi; bunu bilip sinyali kullanıcıya sunmak sorumsuzluk olurdu. Kullanıcı sayfası modelin başarısını ve başarısızlığını şeffafça gösteriyor.
- **Uygulama internetten veri çekmiyor:** Yahoo bizi kendi bilgisayarımızdan bile sık sık engelledi; bulut sunucularından daha da kötü olur. Veriyi yerel taraf güncelliyor, uygulama sadece okuyor. Bu, okuma ve yazma işlerini ayırmak gibi yaygın bir mimari kalıp.
- **Depo arayüzü:** Şimdi hesap açmadan SQLite ile geliştirip, yayına alırken tek bir sınıfı değiştirerek Supabase'e geçebiliyoruz (adaptör kalıbı).
- **`st.cache_data`:** Veri ve ağır hesaplar bir saat önbellekte tutuluyor; her tıklamada 100 dosyayı yeniden okumak gerekmiyor.
- **Dürüst özet kutuları:** Model ve portföy sekmelerinde sonuçların olumsuz olduğu en üstte açıkça yazıyor.

### Olası mülakat soruları
**S: Neden modelin sinyallerini kullanıcıya göstermiyorsun? O zaman model ne işe yarıyor?**
C: İki sebep var: hukuki (SPK'nın yatırım danışmanlığı düzenlemesi) ve etik (backtest modelin avantajı olmadığını gösterdi). Model araştırma ve ileri test için var; kullanıcıya modelin gerçek performansını gösteriyorum. Ürün kararlarında "teknik olarak yapabilmek" ile "yapmak doğru mu" ayrı sorular.

**S: Kullanıcı geri bildirimini kötüye kullanılmaya karşı nasıl koruyorsun?**
C: Not 200 karakterle sınırlı, puan sadece +1/-1 olabiliyor (veritabanında CHECK kısıtı), sorgular parametreli (SQL enjeksiyonuna karşı test var) ve her oturumda sekme başına bir geri bildirim alınıyor. Yayında Supabase'in satır düzeyi güvenliği (RLS) ile kullanıcılar sadece ekleme yapabilecek, okuma yapamayacak.

---

## Aşama 4a: Admin sayfası

### Ne yaptık?
- Sadece yerel bilgisayarda çalışan bir yönetici sayfası: durum paneli, duyuru yayınlama/kapatma, geri bildirimleri okuma, güncel model tahminleri, elle veri girişi (sermaye artırımı düzeltmeleri ve hisse listesi), veri işlemleri (güncelleme, doğrulama, Excel, backtest raporu, yaklaşan temettüler).
- Arayüz ince tutuldu; doğrulama, kaydetme ve komut çalıştırma mantığı `src/yonetim.py` içinde ve test ediliyor.

### Neden böyle yaptık?
- **Şifre yerine ağ izolasyonu:** Kullanıcı şifre istemedi. Şifre olmadan güvenli olmanın yolu, sayfayı ağa hiç açmamak: sadece `127.0.0.1` dinleniyor (işletim sistemi düzeyinde doğrulandı) ve başlatma betiğinin koyduğu ortam değişkeni yoksa sayfa kendini kapatıyor. Kod bir gün yanlışlıkla yayına alınsa bile admin işlevleri çalışmaz (derinlemesine savunma).
- **Elle veriye doğrulama ve git kaydı:** Elle girilen veri en kolay bozulan veridir. Kaydetmeden önce kod listede mi, tarih işlem günü mü, oran pozitif mi, tekrar var mı kontrol ediliyor; kayıt git'e commit'leniyor, böylece her değişikliğin ne zaman yapıldığı ve geri alınabilmesi sağlanıyor.
- **Komut beyaz listesi:** Admin sayfası sadece önceden tanımlı komutları çalıştırabiliyor; serbest komut girişi yok.

### Karşılaşılan sorunlar
- Geliştirme sırasında açtığım kullanıcı uygulaması tüm ağ arayüzlerini dinliyordu (aynı Wi-Fi'deki cihazlar erişebiliyordu). Port dinleme kontrolünde fark edip yerel adrese bağladım ve başlatma betiklerine bunu sabitledim.

### Olası mülakat soruları
**S: Şifresiz admin paneli güvenlik açığı değil mi?**
C: Panel ağa açık olsaydı öyle olurdu. Burada panel sadece loopback (127.0.0.1) adresini dinliyor, yani sadece aynı bilgisayardaki kullanıcı erişebilir. Bunu işletim sisteminin dinlenen portlar listesinden doğruladım. Ayrıca kod düzeyinde ikinci bir kontrol var. Bilgisayarın kendisi zaten Windows oturumuyla korunuyor. Panel ileride uzaktan erişilebilir olacaksa şifre ve rol tabanlı yetkilendirme şart olur.

**S: Admin ile kullanıcı uygulaması verilerini nasıl paylaşıyor?**
C: Duyurular ve geri bildirimler ortak bir depo arayüzü üzerinden yazılıp okunuyor. Şimdi yerel SQLite, yayında Supabase (PostgreSQL). Fiyat verisini ise sadece yerel taraf günceller; kullanıcı uygulaması okur.

---

## Aşama 4b: Ücretsiz grafik ve çizim aracı

### Ne yaptık?
- Mum grafiği (günlük/haftalık/aylık), hacim, istenen kadar MA/EMA (okunabilirlik için en fazla 6 çizgi), Bollinger, RSI ve MACD panelleri.
- Çizim araçları: trend çizgisi, yatay destek/direnç (tıklanan fiyat seviyesinde), bölge, serbest çizim, seçili çizimi silme, tümünü silme. Çizim sayısında pratik sınır yok.
- Çizimler kullanıcının tarayıcısında hisse bazında saklanıyor; JSON olarak indirilip başka cihaza yüklenebiliyor.
- Grafiğin altında son kapanış, RSI ve ortalamalara uzaklık; bu değerleri (`chart.son_degerler`) Aşama 5'te ajan da kullanacak.

### Neden böyle yaptık?
- **Özel bileşen:** Streamlit'in hazır Plotly grafiği çizilen şekilleri Python'a geri vermiyor; sayfa yenilenince çizimler kayboluyordu. Derleme (npm) gerektirmeyen tek bir HTML + JS dosyasıyla Streamlit'in bileşen protokolünü kendim uyguladım.
- **Tarayıcıda saklama:** Sunucuda tek bir JSON dosyası yayında herkesin çizimini karıştırır ve sunucu yeniden başlayınca silinir. Tarayıcı depolaması kişiye özel, üyelik gerektirmiyor ve sunucuya yük bindirmiyor. Bedeli: başka cihazda görünmüyor; bunu dışa/içe aktarma ile çözdüm.
- **Yüklenen JSON'u temizleme:** Kullanıcının yüklediği dosya kötü niyetli olabilir (ör. şekil etiketine HTML gömmek). Sadece izinli şekil türleri ve alanları geçiyor; boyut ve sayı sınırı var. Bunun Node ile yazılmış testi var.
- **Bölünmeye göre düzeltilmiş fiyat:** Ham fiyatta bedelsizler %90'lık sahte uçurum yaratır ve ortalamaları bozar; temettüye göre düzeltilmiş fiyat ise geçmişte hiç görülmemiş fiyatlar gösterir. Grafik platformları da genelde bölünmeye göre düzeltilmiş fiyat kullanır.
- **İndikatörler tüm geçmişte hesaplanıp sonra kesiliyor:** Böylece 6 aylık grafikte MA200 ilk günden doğru değer gösteriyor.

### Karşılaşılan sorunlar
- Python testleri bileşenin tarayıcıda çalıştığını gösteremiyordu. Bilgisayardaki Edge'i ekransız modda DevTools protokolüyle süren küçük bir Node betiği yazıp ekran görüntüsü aldım ve tarayıcıdaki JavaScript hatalarını topladım. Görüntüde sağdaki fiyat etiketlerinin kesildiğini, alt tarih etiketlerinin taştığını, ay adlarının İngilizce olduğunu ve açıklama sırasının ters olduğunu gördüm ve düzelttim (Plotly'ye Türkçe yerel ayar tanımladım).
- `from app.bilesenler import grafik` satırı modülü değil aynı adlı fonksiyonu içe aktarıyordu; uygulamanın duman testi bunu yakaladı.
- **Kullanıcı testinde çıkan iki hata:** (1) Backtest'te varsayılan başlangıç 2019 idi; 2019'dan sonra halka arz olan hisselerde bu tarih verinin başlangıcından önceye düşüp hata veriyordu. Testlerim sadece varsayılan hisseyi (THYAO) denediği için kaçmıştı. Düzeltip **100 hissenin her birini her sekmede** deneyen kapsamlı bir test ekledim. (2) Grafik ikinci sekmede olduğu için ilk çizim sırasında görünmüyordu; Plotly gizli bir alanda yazı genişliklerini 0 ölçtüğünden açıklama ve etiketler üst üste biniyordu. Çözüm: bileşen görünür olana kadar çizimi erteliyor (ResizeObserver). Ders: birim testleri geçse de gerçek tarayıcıda, gerçek kullanım sırasıyla (önce başka sekme, sonra grafik) denemek gerekiyor.

### Olası mülakat soruları
**S: Neden hazır bir grafik kütüphanesi (ör. bir trading platformunun grafiği) kullanmadın?**
C: Proje kuralı başka bir platformun tasarımını kopyalamamaktı ve hazır seçeneklerin çoğu çizimleri kaydetmeyi desteklemiyordu. Plotly zaten projede vardı; üzerine ince bir bileşen yazmak hem bağımlılığı azalttı hem de her satırını açıklayabileceğim bir çözüm oldu.

**S: Kullanıcı verisini tarayıcıda saklamanın riskleri neler?**
C: Veri cihaza bağlı kalır ve tarayıcı temizlenince silinir; bu yüzden dışa aktarma var. Güvenlik tarafında localStorage aynı kökenden çalışan her betiğe açıktır; bu yüzden içine sadece temizlenmiş şekil verisi yazıyorum, kişisel veri yazmıyorum. Kullanıcı hesabı gerekseydi çizimleri Supabase'de kullanıcı bazında, satır düzeyi güvenlikle saklardım.
