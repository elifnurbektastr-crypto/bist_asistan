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
