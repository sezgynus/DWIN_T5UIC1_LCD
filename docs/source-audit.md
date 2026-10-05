# Kaynak audit sonucu — 5 Ekim 2026

Bu rapor refactor/modern-klipper-moonraker üzerindeki ilk 10 maddelik LCD
referans uyarlamasının son adımıdır. İlk dokuz değişikliğin son commit'i
[da9bd55](https://github.com/sezgynus/DWIN_T5UIC1_LCD/commit/da9bd55b4a1444bf89755bb8617a1ab5a1996a30).
Bu raporla aynı commit'teki küçük çizim düzeltmeleri de değerlendirmeye dahildir.
Auditin tamamlanması, aşağıdaki açık kusurların giderildiği anlamına gelmez.

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
| 10 Son audit | Bu rapor; aşağıdaki açık bulgular ve aynı commit'teki çizim düzeltmeleri. |

Son audit sırasında bu çalışma içinde giderilen çizim kusurları:

- %100 için iki basamaklı alan üç basamağa çıkarıldı ve başlangıcı x=109 oldu;
  yüzde işareti x=133'te kaldı. Önceki iki basamak alan yeni doğrulamada hata veriyordu.
- Süre artık tamamlanmış dakika üzerinden HH:MM metni olarak çiziliyor;
  3599 saniye 00:59, 3600 saniye 01:00. 100 saat de gösterilebiliyor.
- Sıfıra yuvarlanan küçük negatif değerlerde -0.00 yerine 0.00 kullanılıyor.
- Reconnect sonrası ilk ekran hemen güncelleniyor; input owner, handler çizimini
  güncelleme komutuyla tamamlıyor. Böylece erken dönen termal editörler bir
  sonraki iki saniyelik tick'i beklemiyor. Dirty flag tekrar gönderimi engelliyor.

## Açık bulgular — henüz düzeltilmedi

P0: yanlış hareket/hedef ya da kontrol bütünlüğü; P1: işlevi bozan kusur;
P2: dayanıklılık veya kapsam sınırlaması. Kesin kusur ile risk ayrı belirtilmiştir.

| ID | Öncelik | Kaynak ve kanıt | Sonuç / sonraki düzeltme |
|---|---|---|---|
| A01 | P1 / kesin | dwinlcd._enqueue_input, herhangi bir _action_feedback varken tüm GPIO girdilerini atıyor. error fazında _dispatch_input Enter bekliyor. Fake GPIO yolu error+press için 0 enqueue üretti. | Komut hata ekranı gerçek düğmeyle onaylanamıyor. Bekleme sırasında girdiyi engelle; hata fazında yalnız onay girdisine izin ver. |
| A02 | P0 / kesin | HMI_Zoffset, Enter'da dwin_zoffset gönderiyor; bu alan editöre girişte mevcut offset'ten yüklenmiyor. offset_value=125 ile hiç çevirmeden Enter, SET_GCODE_OFFSET Z=0.0 MOVE=1 üretti. | Mevcut 1.25 mm offset yerine 0 gönderilebilir. Editörün yerel hedefini mevcut runtime offset'ten başlat ve onu onayla. |
| A03 | P1 / kesin | PrinterData.update_variable her tick'te HMI_ValueStruct.offset_value alanını homing_origin*100 ile yazıyor. 150 yerel değer değişmeyen snapshot ile tekrar 0 oldu. | Z offset düzenlemesi durum güncellemesiyle eziliyor. Editör hedefi abonelik modelinden bağımsız olmalı. |
| A04 | P1 / kesin | Draw_Info_Menu, sürüm metninin uzunluğundan negatif x hesaplayabiliyor. 40 karakterlik sürüm fake driver'da ValueError üretti. | Uzun Klipper sürümü Info ekranını kesiyor. Metni önce görünür alana kısalt; sonra merkezle. |
| A05 | P0 / koşullu risk | PrinterData._jog, SAVE/G91/M83/M220/M221/G1/RESTORE dizisi gönderiyor. Klipper gcode.py:_process_commands, need_ack=False olduğunda komut hatasını yeniden yükseltiyor. | G1 reddedilirse RESTORE çalışmayabilir; göreli mod/faktörler kalabilir. Başarılı yol korunuyor, hata yolu için açık toparlanma ve komut engelleme gerekiyor. Fiziksel hareket hatası enjekte edilmedi. |
| A06 | P0 / kaynak + tekrar | _process_input yalnız subscription snapshot epoch'unu kontrol ediyor; pd.state epoch'unu eşleştirmiyor. UI state epoch=1 iken snapshot/event epoch=2 ile dispatch 1 kez çalıştı. postREST ise yeni snapshot epoch'unu komuta guard olarak alıyor. | Reconnect sonrası ilk tick öncesinde eski yetenek/aktif extruder/konumla yeni bağlantıya komut hazırlanabilir. Girdi işlemeden güncel state ve capability epoch'unu eşleştir. |
| A07 | P1 / kesin | update_variable dosya cache'ini yalnız file_revision değiştiğinde geçersiz kılıyor. Epoch 1→2, file_revision=0→0 durumunda _files_loaded=True ve old.gcode korundu. | Bağlantı yokken kaçırılan dosya değişiklikleri görünmeyebilir. Epoch değişiminde dosya cache'ini de düşür. |
| A08 | P2 / kesin API kusuru | Bazı eski çizim API'leri alanları doğrulamadan ortak buffer'a ekliyor. Draw_Line(65536,...) sonrası Frame_Clear(0), AA 03 01 00 00 ... üretti. QR_Code görünür metinden ayrı, sınırsız UTF-8 payload kullanıyor. | Geçersiz API girdisi sonraki paketi bozabilir. Tüm paketleri doğrulandıktan sonra atomik kur; QR boyutu/verisi için ayrıca sınır koy. Aktif UI'de bu geçersiz girdiler görülmedi. |
| A09 | P1 / sınır durumu | UI birçok alan için 3 whole-digit kapasitesi kullanıyor; yeni numeric API 1000 ve üstünü reddediyor. E mutlak konumu, büyük eksen sınırı veya yüksek hız yüzdesi bu alanı aşabilir. | Büyük değerlerde render exception oluşabilir. Arayüz alanlarını/formatını düzenle veya açık taşma gösterimi kullan; yazıcı hedefini sessizce kırpma. |

Bu bulgular audit sonucudur; yeni bir düzeltme turunun başlangıç listesidir.
İlk 10 maddeden sonra kullanıcının yeni komutu beklenir. Donanım testine geçilmez.

## Önceki 30 bulgunun yeniden değerlendirmesi

"Kaynakta giderildi" başarılı kod yolu ve izole test için geçerlidir;
canlı cihaz doğrulaması anlamına gelmez.

| Eski ID | Durum | Kanıt / kalan sınır |
|---|---|---|
| 01 | Kaynakta giderildi | Resume endpoint tek slash ile doğru. |
| 02–04 | Kaynakta giderildi | Temperature/Tune hotend ve bed doğru Future döndüren API'ye bağlı. |
| 05 | Kaynakta giderildi | Paused/terminal istatistikler print_stats ve virtual_sdcard'dan korunuyor. |
| 06–07 | Kaynakta giderildi | Complete/paused/error ekranları açık durum geçişlerinden türetiliyor; %100 çizim düzeltmesi bu commit'te. |
| 08 | Kaynakta giderildi | speed_factor → feedrate_percentage güncelleniyor; A09 büyük değer sınırı açık. |
| 09 | Kaynakta giderildi | homed_axes üyelikleri her snapshot'ta yeniden hesaplanıyor. |
| 10 | Hareket yolu düzeltildi | _jog, gcode_move.position ile relative delta kullanıyor; editöre giriş command-space. Move menüsünün ilk sayıları hâlâ toolhead.position'dan geliyor, dönüşüm altında ekran/başlangıç gösterimi farklı olabilir. A06 da açık. |
| 11 | Başarılı yolda giderildi | G91/M83, SAVE/RESTORE ve hız/flow faktörleri var; hata yolu A05 açık. |
| 12–13 | Kaynakta giderildi | Menüde G92 E0 yok; hedef fiziksel position'a yazılmıyor; extrusion delta sınırı config'den. |
| 14 | Akış ayrıldı | Manual probe/TESTZ/ACCEPT/ABORT ve ayrı SAVE_CONFIG mevcut; canlı kalibrasyon doğrulanmadı. |
| 15 | Model ayrıldı, editör açık | Runtime homing_origin ve probe pending offset ayrı; A02/A03 nedeniyle runtime editörü henüz hazır değil. |
| 16 | Kaynakta giderildi | Effective config, optional devices, aktif extruder ve eksen min/max keşfi var. |
| 17 | Büyük ölçüde giderildi | Bounded HTTP/WS ve Future hataları var; GPIO hata onayı A01 açık. |
| 18 | Alternatif mimariyle giderildi | Bloklayıcı HTTP tek komut worker'ına taşındı; UI thread POST beklemiyor. Async HTTP kütüphanesi kullanılmıyor. |
| 19 | Kaynakta giderildi | Sabit UDS kaldırıldı; WS snapshot/delta, epoch ve reconnect var. |
| 20 | UART sahipliği giderildi | GPIO yalnız queue; çizim ve UART tek owner. Güncel-state/epoch eksikliği A06 ayrı kusur. |
| 21 | Büyük ölçüde giderildi | Path kimliği, cache, değişim notification ve start Future var; reconnect cache A07 açık. |
| 22 | Kaynakta giderildi | Encoder/button/backend/UART close, owner cleanup ve idempotence var. |
| 23–24 | Kaynakta giderildi | AA header, incremental ACK, bounded retry; Read ve tüm brightness aralığı var. |
| 25 | Referans yolu uygulandı | Nokta renk alanı ve ProUI metin sayıları; paket testleri. Fiziksel görünüm ve A08/A09 açık. |
| 26 | Kaynakta giderildi | Fan discovery/yüzde, editor, preset fan ve birleşik cooldown mevcut. |
| 27 | Kaynakta giderildi | Validated versioned JSON, fsync ve atomic replace; ayar hataları loglanıyor. |
| 28 | Kaynakta giderildi | Klipper velocity/accel/SCV/cruise runtime menüsü; eski steps/mm komutu gönderilmiyor. |
| 29 | Paketleme düzenlendi | CLI/env, venv, service user/groups/state directory/journald/restart; gerçek Pi lifecycle bekliyor. |
| 30 | Aktif instance durumu ayrıldı | Seçimler/HMI/thermal/preset instance başına; immutable printer snapshot. Eski class template ve kullanılmayan Marlin sabitleri bakım borcu olarak duruyor. |

## Ek sınırlar

- HMI_Leveling ve HMI_ToggleLanguage çağrıları kaynakta duruyor, fakat ilgili
  özellik/case kapalı olduğu için aktif menüden erişilemiyor. Buzzer.tone hâlâ
  no-op; kabul bildirimi sesinin fiziksel olarak üretildiği iddia edilmez.
- Bazı menü etiketleri sağdaki değer alanıyla görsel olarak çakışabilir; yatay
  clipping tek başına etiket/değer yerleşim politikasını çözmez. Motion yüksek
  hassasiyetli değerleri de görünür alanı aşabilir. Panelde görsel test gerekiyor.
- ProUI UART gönderiminde byte başına 1 µs yazılım gecikmesi kullanıyor. Python
  bir paketi tek write ile gönderip 1 ms bekliyor; Linux/UART zaten byte'ları
  sıraya koyuyor. Gerçek hat zamanlaması ölçülmedi; bu farklılığın hata olduğu
  sonucuna varılmadı.
- Bellek okuma/yazma, flash ve SRAM resim API'leri bu turda eklenmedi.

## Doğrulama ve durma noktası

- `python3 -m unittest discover -s tests -q`: **159 test geçti**, expected failure yok.
- `python3 -m compileall -q .`: geçti.
- `git diff --check`: geçti.
- Fake serial kullanıldı; gerçek GPIO/UART/network açılmadı.
- Testlerin geçmesi açık bulguları geçersiz kılmaz; A01–A09 önceki kapsamın
  dışındaki veya yalnız doğrudan handler testlerinin kaçırdığı yolları gösteriyor.

Sonraki çalışma için önerilen öncelik: A02/A03 ve A06, A05 hata toparlanması,
A01, A07, A04/A09 ve A08. Ardından önceki listenin 11–13. maddeleri olan fiziksel
LCD, canlı Klipper/Moonraker ve Raspberry Pi servis doğrulaması.
