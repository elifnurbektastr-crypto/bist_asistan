# 🧪 Deney Günlüğü

ML modelinde yapılan her iyileştirme denemesi buraya kaydedilir. Başarısız deneyler de silinmez, onlar da öğreticidir.

**Ortak kurulum (tüm deneyler):**
- Walk-forward doğrulama: her yıl başında yeniden eğitim, test yılları 2019-2026, purging ile.
- 81 hisse (en az 5 yıllık geçmiş), yaklaşık 158 bin test satırı.
- Hedef: yarının açılışında al, 5 işlem günü sonraki açılışta sat; getiri TL bazında > 0 mı?
- Çıta: "hep yükselir" tahmini %54,4 doğruluk (TL'deki enflasyon kaynaklı yukarı yönlü eğilim yüzünden %50 değil).

| # | Tarih | Ne değişti? | Sonuç (2019-2026) | Çıtaya göre | Yorum |
|---|---|---|---|---|---|
| 1 | 2026-11-25 | İlk deney: 21 özellik (hisse + endeks + kur + makro), 5 model | LightGBM: doğruluk %47,8, AUC 0,476. Lojistik: %50,9, AUC 0,517 | ❌ Hepsi altında | Ağaç modelleri AUC < 0,5: sistematik olarak ters tahmin. 2022'de LightGBM %38 |
| 2 | 2026-11-25 | Teşhis: özellik setleri karşılaştırıldı (hepsi / makro hariç / sadece hisseye özgü) | LightGBM: %47,8 → %50,5 → **%52,1**, AUC 0,476 → 0,501 → **0,516**. 2022: %38 → %49 → %56 | ❌ Hâlâ altında | En önemli 7 özelliğin 7'si piyasa geneli özellikti (reel faiz başta). Model hisse seçimi yerine "piyasa zamanlaması" öğreniyor ve rejim değişiminde (2022, %80 enflasyon) çöküyordu. **Karar:** varsayılan setten piyasa geneli özellikler çıkarıldı |
| 3 | 2026-11-25 | Hiyerarşik yaklaşım (temiz özelliklerle): ortak model, korelasyon grupları (5 grup), hisseye göre ince ayar (+40 ağaç) | Ortak: %52,1 / 0,516. Grup: %52,0 / 0,516. İnce ayar: **%52,3** / 0,516 | ❌ Doğrulukta altında | Farklar 0,3 puanın altında, anlamlı değil. Hisseye özel ince ayar belirgin bir kazanç getirmedi. Varsayılan: ince ayar (en yüksek doğruluk, güçlü sinyal isabeti) |
| 4 | 2026-11-25 | Olasılık eşiği: sadece model emin olduğunda sinyal | p > 0,60: kapsama %14, isabet **%57,9**, ort. 5g getiri **%1,43** (tüm günler: %1,01) | ✅ Seçili dilimde çıtanın üstünde | Model en emin olduğu %14'lük dilimde 5 günde ortalamanın 0,42 puan üstünde getiri yakaladı. Komisyon (%0,2 gidiş-dönüş) sonrası anlamlı mı? → Aşama 3 backtest |
| 5 | 2026-11-25 | Hedef değişikliği: 20 günlük gelecek volatilitesi (regresyon) | LightGBM: ort. hata 0,110, R² 0,20, sıralama korelasyonu 0,50. Çıta (geçmiş vol): 0,140, R² -0,17, 0,42 | ✅ Her yıl çıtanın üstünde | Volatilite yön tahmininden çok daha tahmin edilebilir (volatilite kümelenmesi). Risk yönetimi için kullanılabilir |

**Hatırlatma:** Doğruluk birden %65'in üstüne çıkarsa önce veri sızıntısı (look-ahead bias) ve aşırı öğrenme kontrol edilir, sonuç ondan sonra kabul edilir. Bu deneylerde alarm tetiklenmedi.

## Sıradaki deney fikirleri
- Piyasa geneli özellikleri seviye değil **değişim** olarak eklemek (ör. enflasyondaki aylık değişim): rejim seviyesine bağımlılığı azaltabilir.
- Hedefi göreli tanımlamak (o gün hisselerin ortanca getirisini geçer mi?): piyasa etkisini tamamen çıkarır.
- Hiperparametre ayarı: sadece eğitim dönemi içinde iç walk-forward ile.
- Volatilite tahminini backtest'te pozisyon büyüklüğü için kullanmak.


## Aşama 3: Backtest ile doğrulama (2026-11-25)

| # | Ne test edildi? | Sonuç (2019-01 → 2026-11, maliyet işlem başı %0,15) | Hüküm |
|---|---|---|---|
| 6 | ML ilk 10 portföyü (5 günde bir dengeleme), eşik 0,60 ve 0,50 | Yıllık %34,9 / %35,3; eşit ağırlıklı 81 hisse %56,2; rastgele 10 hisse %37,7; XU100 %39,0 | ❌ Model rastgele seçimi bile geçmiyor |
| 7 | Volatilite tahminine göre ağırlık (ters volatilite) | %34,9, maks. düşüş -%34,9 (eşit ağırlıklı ML: -%35,5) | ➖ Etkisi yok denecek kadar küçük |
| 8 | Maliyet duyarlılığı | Maliyet sıfırken ML %43,6-49,9, eşit ağırlık %56,3 | ❌ Sorun sadece maliyet değil; maliyetsiz de geride |
| 9 | Nakit faizi | ML 0,60 zamanın %44'ünde nakitte; faiz olmadan yıllık %19,3 | ⚠️ Seçici eşiğin görünen getirisinin büyük kısmı faiz |

**Ders:** Deney 4'teki "güçlü sinyalde ort. 5g getiri %1,43, ortalama %1,01" sonucu, farklı günlerin hisseleri havuzlanarak hesaplandı. Bu fark büyük ölçüde zamanlamadan (piyasanın genel olarak yükseldiği günler) geliyor; aynı gün içinde hisse seçimi (portföyün yaptığı iş) için bir avantaj sağlamıyor. Bundan sonra model değerlendirmesinde **gün içi sıralama metrikleri** (ör. günlük ilk-son dilim farkı, günlük AUC ortalaması) ana metrik olmalı.
