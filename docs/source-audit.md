# Kaynak audit sonucu — 5 Ekim 2026

İlk 10 referans uyarlaması tamamlandı. Sonrasında bulunan **A01–A09 kaynakta
giderildi** ve regresyon testleri eklendi. Fiziksel LCD, canlı yazıcı ve Raspberry
Pi servis testleri yapılmadı. Önceki bulguların değişmeden saklanan raporu:
[ilk audit](https://github.com/sezgynus/DWIN_T5UIC1_LCD/blob/2f954aaec3b2ced77d61f877cbb4d9fefc12cbc6/docs/source-audit.md).

## Referans ve kapsam

- LCD: [mriscoc 05903a80](https://github.com/mriscoc/Ender3V2S1/tree/05903a80d6e15cc91b0bc690b35e08fd440a21e9).
  common/dwin_api.{cpp,h}, common/dwin_set.h, proui/dwin_lcd.{cpp,h},
  proui/dwinui.{cpp,h}, proui/dwin.cpp ve stock DWIN_SET incelendi.
- Önceki Klipper referansı:
  [461c4e37](https://github.com/Klipper3d/klipper/tree/461c4e3722c3a897fba1c6b3f0780a5315043842).
- Önceki Moonraker referansı:
  [9e676eba](https://github.com/Arksine/moonraker/tree/9e676eba6b02661a4dfa3ec6e7ac3f3504498e6d).
- Uygulamanın 14 Python modülü; testler; README; requirements; servis ve örnek
  ortam ayarları incelendi. AST/çağrı taramaları ve fake I/O ile doğrudan kusur
  tekrarları yapıldı. Fiziksel LCD, canlı Moonraker veya yazıcı kullanılmadı.
- ProUI sayıları 0x11 metin komutuyla çiziyor. Eski Creality/Jyers 0x14
  implementasyonu, ProUI'nin aktif sayısal çizim yolu olarak değerlendirilmedi.

## İlk 10 maddenin sonucu

| Madde | Sonuç |
|---|---|
| 1 Sayısal çizim | Ölçekli Python API korunarak ProUI tarzı metin, alan doldurma, yuvarlama ve işaret alanı uygulandı. |
| 2 Görsel bayraklar | IBD/BIR/BFI seçenekleri eklendi; varsayılan şeffaf güçlendirilmiş filtreleme. |
| 3 Animasyon kontrolü | 0x29 ve 16-bit maske doğrulaması. |
| 4 Parlaklık | 0 dahil tüm byte aralığı korunuyor. |
| 5 Başlangıç | 750 ms uyanma, bounded handshake, yön 1; örtük JPG 0 kaldırıldı. |
| 6 Güncelleme | Dirty flag; gereksiz 0x3D gönderimi yok. |
| 7 Metin | Font/ekran/payload sınırı; ASCII ve Türkçe transliterasyon politikası. |
| 8 Görsel kaynaklar | 91 ikon ve 50 sabit kopyalama bölgesi; stock dosya hash envanteri. Kurulu panel dosyaları bilinmiyor. |
| 9 Regresyon | Referanstan çıkarılan paketler ve gerçek menü/tek UART owner kontrolleri. |
| 10 Son audit | Kaynak taraması ve ardından A01–A09 düzeltme turu. |

Son audit sırasında bu çalışma içinde giderilen çizim kusurları:

- %100 için iki basamaklı alan üç basamağa çıkarıldı ve başlangıcı x=109 oldu;
  yüzde işareti x=133'te kaldı. Önceki iki basamak alan yeni doğrulamada hata veriyordu.
- Süre artık tamamlanmış dakika üzerinden HH:MM metni olarak çiziliyor;
  3599 saniye 00:59, 3600 saniye 01:00. 100 saat de gösterilebiliyor.
- Sıfıra yuvarlanan küçük negatif değerlerde -0.00 yerine 0.00 kullanılıyor.
- Reconnect sonrası ilk ekran hemen güncelleniyor; input owner, handler çizimini
  güncelleme komutuyla tamamlıyor. Böylece erken dönen termal editörler bir
  sonraki iki saniyelik tick'i beklemiyor. Dirty flag tekrar gönderimi engelliyor.

## Dokuz bulgunun kapanışı

| ID | Düzeltme ve doğrulama | Commit |
|---|---|---|
| A01 | Hata fazında gerçek GPIO Enter girdisi onayı mümkün; bekleme girdileri engelleniyor. Producer→owner regresyonu. | eddca211 |
| A02 | Z offset Enter, mevcut runtime offset ile başlatılan editör hedefini gönderiyor; sonlu değer ve aralık kontrolü var. | fc2f5d5 |
| A03 | Editör hedefi abonelik alanından ayrıldı; tick kullanıcının düzenlemesini ezmiyor. Prepare ve Tune aynı giriş yolunu kullanıyor. | 3bcfb8b |
| A04 | Info metni panel politikasına çevrilip kısaltıldıktan sonra merkezleniyor; uzun sürüm negatif koordinat üretmiyor. | 0e3ceb8 |
| A05 | SAVE ayrı istekte doğrulanıyor. Hareket hatasında yalnız RESTORE MOVE=0 deneniyor; belirsiz durumda yeni hareket/baskı engelleniyor ve açık kurtarma seçeneği gösteriliyor. Hareket tekrar gönderilmiyor. | 96cd675 |
| A06 | Her encoder adımından önce state/capability epoch eşleştiriliyor; menü değişirse girdi atılıyor. Backend de eski state ile yeni bağlantıya komut göndermiyor. | c0b6a03 |
| A07 | Epoch değişiminde dosya listesi ve UI dosya görünümü geçersiz kılınıyor; aynı revision eski cache'i korumuyor. | 600399e |
| A08 | Yüksek seviyeli UART paketleri bütün alanları doğruladıktan sonra atomik kuruluyor. QR UTF-8 byte boyutu ve pixel sınırı kontrol ediliyor. Hatalı çağrı sonraki paketi bozmuyor. | 7ef391c |
| A09 | Sayısal taşma exception yerine alan genişliğinde # işareti çiziyor; gerçek hedef değişmiyor. İşaret geçişleri alanı temizliyor, Motion değerleri gerektiğinde tam bilimsel gösterim kullanıyor. | Bu raporla aynı commit |

Son kontrol ayrıca hiç gönderilmeden reddedilen/iptal edilen jog'un gereksiz
kurtarma engeli bırakmamasını doğrular. Buna karşılık iptal edilen açık RESTORE,
belirsiz durumu temizlemez; yalnız doğrulanmış RESTORE başarısı engeli kaldırır.

## Doğrulama ve sınırlar

- `python3 -m unittest discover -s tests -q`: **185 test**, expected failure yok.
- `python3 -m compileall -q .` ve `git diff --check`.
- Fake serial/HTTP/GPIO kullanılıyor; kaynak ve hata yolları sınanıyor.
- Jog engeli bu LCD istemcisini kapsar; diğer Moonraker istemcilerini kilitlemez.
  Kurtarma bilgisi süreç belleğindedir. Klipper yeniden başlatılıp kayıtlı state
  kaybolursa başarısız RESTORE engeli kaldırmaz.
- Move menüsünün ilk değerleri toolhead.position, editör ve hareket ise command
  space kullanır; dönüşümler altındaki ilk ekran gösterimi ayrıca incelenmelidir.
- Kurulu panel asset dosyaları, gerçek UART zamanlaması ve metin/değerlerin panel
  üzerindeki görsel yerleşimi henüz doğrulanmadı. Buzzer.tone no-op olarak kalır;
  kapalı leveling/language yolları ve kullanılmayan Marlin sabitleri bakım borcudur.
- Bellek/flash/SRAM resim API'leri bu kapsamda eklenmedi.

A01–A09 kapanışı tüm donanım davranışlarının doğrulandığı anlamına gelmez.
Önceki listenin 11–13. maddeleri (fiziksel LCD, canlı Klipper/Moonraker ve Pi
kurulum/servis doğrulaması) kullanıcının yeni komutunu bekler.
