# MMU menüsü — resimli kullanım taslağı

**Bu belge önerilen arayüzün nasıl çalışacağını anlatır. Henüz MMU kontrol implementasyonu değildir.** Görseller 272×480 için hazırlanmış örnek verilerdir; gerçek cihaz ekran görüntüsü değildir. Menü yazıları mevcut arayüze uygun İngilizce, açıklamalar Türkçedir.

## Kullanım mantığı

**Çevir → odak değiştir. Bas → seç/aç.** Değer düzenlerken ilk basış düzenlemeyi açar, çevirme değeri değiştirir, ikinci basış değeri kabul eder. Kaydetme gereken ekranlarda **Save** ayrıca seçilir. Sol üstteki geri oku encoder ile seçilir; uzun basış mevcut güç davranışı için korunur.

MMU ekran ailesinde alttaki genel hareket paneli tamamen kalkar. Bu bize **120 piksel** ek alan kazandırır. Isı, yalnız MMU işlemiyle ilgili bölümlerde gösterilir.

## Bir bakışta

![Günlük MMU kullanımı ve alt menüler](https://github.com/sezgynus/KlipperDWIN/blob/docs/mmu-menu-demo/docs/mmu-menu-demo/daily-overview.png?raw=true)

![Bakım ve kurtarma akışları](https://github.com/sezgynus/KlipperDWIN/blob/docs/mmu-menu-demo/docs/mmu-menu-demo/recovery-overview.png?raw=true)

## Ekranlar nasıl çalışacak?

### 1. MMU açılış ekranı

![MMU açılış ekranı](https://github.com/sezgynus/KlipperDWIN/blob/docs/mmu-menu-demo/docs/mmu-menu-demo/home.png?raw=true)

Ana menüde MMU seçilip düğmeye basılınca açılır. Alt genel hareket göstergeleri kalkar. Üstte makaralar, ortada aktif takım/kanal ve filament yolu, altta altı menü girişi bulunur. Encoder çevrilince mavi odak sırayla düğmeler arasında dolaşır; basılınca seçilen menü açılır. Yeşil G3 aktif kanaldır, mavi odakla aynı anlamı taşımaz. Sol üstteki geri oku da seçilebilir. Yüklü filamentte Unload görünür; uygun boş durumda bunun yerini Load alır.

### 2. Kanallar: hangi makarada ne var?

![Kanallar: hangi makarada ne var?](https://github.com/sezgynus/KlipperDWIN/blob/docs/mmu-menu-demo/docs/mmu-menu-demo/gates.png?raw=true)

Gates ile bu liste açılır. Encoder ile bir kanala gidilir, basılınca o kanalın işlem ekranı açılır. Listede gezinmek fiziksel kanal seçimi veya filament hareketi yapmaz. Dörtten fazla kanal varsa liste kayar/sayfalanır. Yüzdeler Spoolman verisidir; veri yoksa -- yazılır.

### 3. Kanal işlemleri

![Kanal işlemleri](https://github.com/sezgynus/KlipperDWIN/blob/docs/mmu-menu-demo/docs/mmu-menu-demo/gate.png?raw=true)

Örnekte T2'ye bağlı G3 yüklüdür. Unload filamenti MMU'ya geri park eder; Eject spool makarayı MMU'dan çıkarır ve gerekiyorsa önce boşaltır. Her hareket için hedefi açıklayan onay gösterilir. Filament boşken uygun Select only, Load/change, Preload ve Check seçenekleri açılır; bunlar uygulamada ayrı seçilebilir işlemler olacaktır. Select only yüklemeden kanal seçer; Load/change ise yükleme/takım değiştirme akışıdır. LOCK görünen işlem o an çalıştırılamaz.

### 4. Filament ve Spoolman

![Filament ve Spoolman](https://github.com/sezgynus/KlipperDWIN/blob/docs/mmu-menu-demo/docs/mmu-menu-demo/filament.png?raw=true)

Kanalın malzemesi, rengi, makara kimliği, kalan yüzdesi ve sıcaklık bilgisi görünür. Assign spool ID ile kimlik alanı açılır: basarak düzenlemeye girilir, çevirerek sayı değiştirilir, tekrar basarak değer onaylanır; atama ayrıca kaydedilir. Spoolman bağlantısının modu değişikliğe izin vermiyorsa bu işlem de kapanır. Metadata salt okunur olabilir. Uzun isim ve serbest renk düzenlemesini web arayüzünde bırakmayı öneriyorum.

### 5. Takım–kanal eşleme

![Takım–kanal eşleme](https://github.com/sezgynus/KlipperDWIN/blob/docs/mmu-menu-demo/docs/mmu-menu-demo/map.png?raw=true)

Önce takım satırına gelinip basılır; ardından encoder çevrilerek bağlanacağı fiziksel kanal değiştirilir. Tekrar basmak düzenlenen değeri kabul eder. Save tüm taslağı uygular, Cancel değişiklikleri bırakır. Örnekte T2 → G3. Ekranda G1, Happy Hare tarafındaki GATE=0 demektir; takım numaraları T0'dan başlamaya devam eder. Baskı sırasında eşleme düzenleme kapalıdır.

### 6. EndlessSpool

![EndlessSpool](https://github.com/sezgynus/KlipperDWIN/blob/docs/mmu-menu-demo/docs/mmu-menu-demo/endless.png?raw=true)

Tool map içindeki EndlessSpool girişinden açılır. Özelliği açıp kapatabilir ve kanal gruplarını düzenleyebilirsin. Örnekte G1 ve G2 aynı gruptadır; G1 biterse Happy Hare uygun koşullarda G2'ye geçebilir. Grup satırına basmak üye kanal seçimini açar; Save uygulanana kadar değişiklikler taslaktır. Aynı gruptaki malzeme ve renklerin uygunluğunu kullanıcı görerek kontrol etmelidir.

### 7. Bakım menüsü

![Bakım menüsü](https://github.com/sezgynus/KlipperDWIN/blob/docs/mmu-menu-demo/docs/mmu-menu-demo/manage.png?raw=true)

Manage; kurtarma, selector/gate kontrolü, grip/release, extruder-only, motor/senkronizasyon ve seçeneklere giriş verir. Normal bakım işlemleri baskı dışında ve uygun filament durumunda açılır. Hata nedeniyle duran baskıda Recover ekranına ayrı bir doğrudan giriş bulunur. Donanımın desteklemediği servo/selector işlemleri sunulmaz. Kalibrasyon ilk sürümde web arayüzünde kalır.

### 8. Bakım işlemleri

![Bakım işlemleri](https://github.com/sezgynus/KlipperDWIN/blob/docs/mmu-menu-demo/docs/mmu-menu-demo/maintenance.png?raw=true)

Bu örnek boş filamentli, uygun çalışma durumundaki selector + servo sistemini gösterir. Home selector başlangıç referansını bulur, Check all gates kanal doluluğunu kontrol eder. Grip/release mekanizmayı tutar veya bırakır; extruder-only komutları yalnız ekstrüder bölümünü yönetir. Ekrandaki seçenekler MMU tipine göre değişir. Hareket seçilince hedefli onay ve ardından canlı durum gösterilir.

### 9. MMU seçenekleri

![MMU seçenekleri](https://github.com/sezgynus/KlipperDWIN/blob/docs/mmu-menu-demo/docs/mmu-menu-demo/options.png?raw=true)

Destek varsa MMU etkinliği, LED modu, gear sync, motor bırakma ve sensör/FlowGuard sayfaları burada bulunur. Tek ünite varsa gereksiz ünite seçici gösterilmez; birden fazla ünitede seçim açılır. Bunlar örnek seçeneklerdir; mevcut sürüm, donanım ve yazıcı durumu hangi işlemin açık olacağını belirler. Motor bırakma gibi işlemler ayrıca onay ister.

### 10. Hata ve kurtarma

![Hata ve kurtarma](https://github.com/sezgynus/KlipperDWIN/blob/docs/mmu-menu-demo/docs/mmu-menu-demo/recover.png?raw=true)

MMU baskıyı hata nedeniyle durdurursa hata nedeni, takım/kanal ve bilinen filament durumu gösterilir. Önce fiziksel problem düzeltilir, sonra Auto recover ile durum kontrol edilir. Gerekirse Set state manually açılır. Unlock/reheat hata kilidi/ısıtma adımıdır; Resume print ayrı bir karardır. Demo kilitli durumda olduğu için Resume kapalıdır; gerekli koşullar sağlanınca açılır.

### 11. Elle durum bildirme

![Elle durum bildirme](https://github.com/sezgynus/KlipperDWIN/blob/docs/mmu-menu-demo/docs/mmu-menu-demo/manual.png?raw=true)

Tool, Gate ve Filament alanları encoder ile düzenlenir. Apply mevcut fiziksel durumu Happy Hare'e bildirir; bu ekran filamenti yükleyip boşaltmaz. Örneğin filament elle çıkarıldıysa UNLOADED bildirilebilir. Yanlışlıkla durum değiştirmemek için uygulamada hedefi özetleyen bir onay gerekir. Cancel önceki ekrana değişiklik yapmadan döner.

### 12. Canlı işlem ve sensörler

![Canlı işlem ve sensörler](https://github.com/sezgynus/KlipperDWIN/blob/docs/mmu-menu-demo/docs/mmu-menu-demo/status.png?raw=true)

Bir işlem başlayınca bu görünüm hangi aşamada olduğunu gösterir. Örnekte Bowden yüklemesi %68'dir; bu tüm takım değişiminin veya toplam sürenin %68'i değildir. Sensörler, gear sync ve nozzle ısısı görünür. Yüzde verisi gelmiyorsa aşama adı gösterilir; uydurma ilerleme üretilmez. Yüklü/boş tahmini ile fiziksel sensör okuması ayrı tutulur.

### 13. Bypass: doğrudan ekstrüdere makara

![Bypass: doğrudan ekstrüdere makara](https://github.com/sezgynus/KlipperDWIN/blob/docs/mmu-menu-demo/docs/mmu-menu-demo/bypass.png?raw=true)

MMU filamenti yüklüyken önce Unload current gate seçilir. Boşaltma tamamlanınca Select bypass açılır; bypass seçilince extruder-only yükleme/boşaltma kullanılabilir. Ekranın kilitleri gerçek durumla değişir. Böylece MMU filamentini içeride bırakıp doğrudan makarayla çakışan bir akış başlatılmaz.

### 14. Hareket öncesi onay

![Hareket öncesi onay](https://github.com/sezgynus/KlipperDWIN/blob/docs/mmu-menu-demo/docs/mmu-menu-demo/confirm.png?raw=true)

Örnekte Unload T2/G3 onayı var. İlk odak Cancel üzerindedir. Çevirip Unload'a gelerek basmak hareketi başlatır; Cancel geri döner. Eject, motor bırakma ve diğer işlemler kendi adını/hedefini gösteren ayrı onay kullanır. Komutun gönderilmiş olması tamamlandığı anlamına gelmez; durum ekranı gerçek sonucu bekler.


## Üç örnek kullanım

**Makara değiştirmek:** MMU → Gates → hedef kanal → Eject spool → hedefi kontrol et ve onayla → işlemin bitmesini bekle → yeni filamenti yerleştir → Preload / Check → gerekiyorsa Load/change.

**Başka takıma geçmek:** MMU → Gates → hedef kanalın işlemleri. Önce mevcut filamentin durumu değerlendirilir; uygun Load/change akışı seçilir. Sadece listede gezinmek veya detay açmak herhangi bir hareket yaptırmaz.

**Hata sonrası devam etmek:** Hata nedenini oku → fiziksel sorunu düzelt → Auto recover veya doğru manuel durum bildirimi → gerekiyorsa Unlock/reheat → koşullar uygun olduğunda Resume print.

## Önerdiğim uygulama sırası

1. Tam ekran MMU, canlı durum, kanallar, temel hareketler, bypass ve hata kurtarma.
2. Takım–kanal eşleme, EndlessSpool ve Spoolman kimlik atama.
3. Donanıma bağlı gelişmiş seçenekler ve çoklu ünite görünümü.

Uzun isim/RGB düzenleme, kapsamlı kalibrasyon ve purge matrisi ilk aşamada web arayüzünde kalır.

---

<details>
<summary><strong>Kaynak incelemesi, uygulanabilirlik ve teknik ayrıntılar</strong></summary>

7 Ekim 2026 · Konsept ve uygulanabilirlik çalışması

Kaynak incelemesi yalnız GitHub üzerindeki sezgynus/KlipperDWIN reposundan yapıldı. İncelenen master ağaç kimliği: 55a0bd70894673d679dcad3571d9802594db777f. İnceleme sırasında uygulama kodu değiştirilmedi; bu dal yalnız tasarım belgelerini içerir. Görseller gerçek cihaz ekran görüntüsü değildir; 272×480 yerleşim demolarıdır. Değerler örnektir. Yazılar repo ile uyumlu İngilizce/ASCII tutuldu; LCD fontu çizimleri yaklaşık temsil edilir.

## Karar
Günlük MMU kullanımı ve hata kurtarma DWIN üzerinde uygulanabilir. Web arayüzünün bütün düzenleme araçlarını aynı küçük ekrana taşımak gerekli değil. Ana ekran, dört makara ve aktif filament durumunun altında altı kısa giriş kullanır. Encoder çevirme yalnız odağı değiştirir; basma alt menüyü açar. Fiziksel hareket, açıkça seçilen işlemle başlar.

Alt genel gösterge paneli MMU ailesinin tüm ekranlarında kalkar. Ekran yüksekliği 480 piksel; mevcut durum paneli y=360'ta başlıyor. Böylece 120 piksel, yani toplam ekranın %25'i geri kazanılır. Ana başlık 30 piksel kalır. Isı bilgisi MMU yükleme ve kurtarma bağlamında ayrıca gösterilir.

## Kaynakta görülen mevcut temel
- ui_mmu.py içindeki Draw_MMU_Menu yalnız başlık ve Back çiziyor; HMI_MMU_Menu basıldığında ana menüye dönüyor.
- Ana menü girişi ve makara çizimi var. Renk, kanal durumu, aktif kanal, Spoolman kalan yüzdesi ve çıkış LED rengi zaten ele alınıyor.
- printerInterface.py MMU nesnesini normalize ediyor; yeni ekranların ihtiyaç duyduğu işlem, takım, eşleme, hata ve sensör alanlarını bu modele eklemek gerekir.
- Moonraker aboneliği mmu ve mmu_machine nesnelerini keşfediyor. Kontrol için mevcut komut/sonuç altyapısı kullanılabilir.
- DWIN_Screen.py 272×480, 115200 baud, RGB565, çizgi/dikdörtgen ve 6×12, 8×16, 10×20 gibi sabit font ölçülerini destekliyor. ASCII normalizasyonu nedeniyle Türkçe harfleri doğrudan LCD fontunda varsaymamak gerekir.

Kaynaklar: [MMU ekranı](https://github.com/sezgynus/KlipperDWIN/blob/master/ui_mmu.py), [ana UI](https://github.com/sezgynus/KlipperDWIN/blob/master/dwinlcd.py), [veri modeli](https://github.com/sezgynus/KlipperDWIN/blob/master/printerInterface.py), [ekran sürücüsü](https://github.com/sezgynus/KlipperDWIN/blob/master/DWIN_Screen.py).

## Resmi arayüzle karşılaştırma
Happy Hare'in güncel resmi belgeleri v4'ü esas alıyor. v3 ayrı dalda bulunuyor; kullanıcının yazıcısında kurulu sürüm bu çalışmada doğrulanmadı. V4 veya v3 komut/veri uyumluluğu çalışma zamanında kontrol edilmeli.

Resmi KlipperScreen paneli kanal bağlamında seçme, kontrol, ön yükleme, yükleme, boşaltma ve çıkarma işlemlerini sunuyor. Bakım ve durum kurtarma; filament bilgileri; takım–kanal eşleme ve EndlessSpool ayrı ekranlarda. DWIN için aynı görevleri küçük sayfalara böldüm. Güncel maintainer arayüzleri, Mainsail/Fluidd ana sürümlerinden ileride olabilir; bütün özelliklerin her kurulumda mevcut olduğu varsayılmamalı.

Kaynaklar: [Happy Hare README](https://github.com/moggieuk/Happy-Hare/blob/main/README.md), [resmi KlipperScreen](https://moggieuk.github.io/Happy-Hare-Doc/KlipperScreen/), [resmi Mainsail/Fluidd](https://moggieuk.github.io/Happy-Hare-Doc/Mainsail-Fluidd-Integration/).

| İşlev | DWIN önerisi | Kapsam |
|---|---|---|
| Aktif takım/kanal, filament ve işlem | Ana ekran + Status | İlk sürüm |
| Kanal seçme, yükleme, boşaltma, eject, preload, check | Gates > kanal işlemleri | İlk sürüm |
| Bypass | Ayrı bağlamsal ekran | İlk sürüm |
| Hata nedeni, otomatik kurtarma, manuel durum | Recover | İlk sürüm |
| Malzeme, renk, Spool ID, kalan yüzde | Filament özeti | İlk sürüm; yüzde Spoolman verisine bağlı |
| Takım–kanal eşleme | Encoder ile satır düzenleme ve Save | İkinci adım |
| EndlessSpool grupları | Basit grup listesi | İkinci adım |
| Sensörler, gear sync, encoder/FlowGuard özeti | Status ve Options | Donanıma bağlı |
| Home, grip/release, extruder-only, motor bırakma | Manage | Donanıma ve çalışma durumuna bağlı |
| Çoklu MMU | Ünite seçimi + global kanal numarası | Modelde baştan destek; ayrı UI genişletmesi |
| Uzun isim, serbest renk/RGB ve geniş Spoolman arama | Web arayüzü | DWIN'de mümkün ama elverişsiz |
| Kapsamlı kalibrasyon, purge matrisi, ayrıntılı istatistik | Web arayüzü | İlk sürüm dışı |
| Kurutucu, NFC/TD-1, eSpooler gelişmiş yönetimi | İleride donanım alt sayfaları | İlk sürüm dışı |

## Demo ekranları
1. home.png — MMU açılış ekranı; makara durumu, aktif T2/G3, filament yolu, nozzle ve alt menüler.
2. gates.png — Kanal listesi. Bu ekranda gezinmek MMU'yu hareket ettirmez.
3. gate.png — Yüklü kanal örneği; geçersiz işlemler kilitli.
4. filament.png — Spoolman bağlantılı filament özeti. Metadata salt okunur olabilir; spool atama ayrı bir yetkidir.
5. map.png — Takım–kanal eşleme, kayıt öncesi taslak.
6. endless.png — Gruplar ve aç/kapa.
7. manage.png — Bakım görevlerine giriş.
8. recover.png — MMU hata kilidi ve neden; kurtarma seçenekleri.
9. manual.png — Gerçek fiziksel durumu Happy Hare'e bildirme.
10. status.png — Yükleme aşaması ve sensörlerin örnek görünümü.
11. bypass.png — MMU'da filament yüklüyken bypass geçişinin engellenmesi.
12. confirm.png — Unload onayı, varsayılan Cancel.
13. maintenance.png — Filament boş ve yazıcı uygun durumdayken örnek bakım işlemleri.
14. options.png — Yeteneğe bağlı MMU seçenekleri.

Bunlar farklı durumları gösteren statik tasarımlardır; aynı anda gerçekleşen bir oturum veya çalışan kontrol yazılımı değildir. Ana örnek dört kanallıdır. Fazla kanal için dört makara/sayfa ve kaydırılabilir kanal listesi kullanılmalı; sayı büyüdükçe makaralar okunamaz kadar küçültülmemeli.

## Etkileşim ve durum kuralları
- Ekrandaki G1, API tarafında GATE=0'dır; bu mevcut home makara numaralandırmasını korur. T0 aynı kalır. Dönüşüm yalnız sunum sınırında yapılır; kaynaklardaki gate değerleri sıfır tabanlıdır.
- Mavi odak ile yeşil aktif kanal farklı anlam taşır. LED rengi kanal doluluğunun tek kanıtı olmamalı.
- Back her ekranda encoder ile seçilebilir. Uzun basma mevcut güç davranışıyla çakışabileceğinden geri dönüşe atanmaz.
- Boş/yüklü/bilinmiyor, MMU kapalı, çevrimdışı ve işlem sürüyor durumları ayrı ele alınır. Güncel veri yoksa hareket komutları kapanır.
- Baskı sırasında sıradan kanal değişimi/eşleme/bakım kapanır; izleme ve uygun pause/recovery akışı kalır.
- Komut gönderimi başarı değildir. Bekleme görünümü gerçek MMU durumuyla güncellenir; hata mesajı kaybolmaz.
- Unload MMU'ya geri park eder. Eject MMU'dan çıkarır; yüklü filamentte gerekirse önce unload içeren işlem yapar. Eject için kendi hedefli onay ekranı gerekir.
- Auto recover, manuel düzeltme, unlock/reheat ve Resume birbirinden ayrılır. Kilidi açmak otomatik baskıya devam anlamına gelmez.
- Yalnız Bowden hareketine ait yüzde mevcutsa gösterilir. Aşama yüzdesi toplam işlem süresi diye sunulmaz.
- Fiziksel sensör durumları ile Happy Hare'in tahmini filament konumu ayrı bilgiler olarak gösterilir. Eksik sensör CLEAR diye çizilmez; yok/devre dışı/bilinmiyor olarak belirtilir.
- Spoolman başarısızsa kalan yüzde -- olur. Makara yüzdesi filament rengine veya yüklenme durumuna bakılarak uydurulmaz.
- EndlessSpool aynı grupta farklı renk/malzeme bulunmasını kullanıcıya görünür kılmalı; bu demo yalnız grup düzenini örnekler.

## Komut ve veri bağlantıları
Temel komutlar: MMU_SELECT GATE=n yalnız seçim; MMU_CHANGE_TOOL TOOL=n takım değişimi; MMU_LOAD mevcut kanaldan yükleme; MMU_UNLOAD park; MMU_EJECT GATE=n çıkarma; MMU_PRELOAD GATE=n ve MMU_CHECK_GATE GATE=n hazırlık/kontrol.

Bypass seçiminden sonra EXTRUDER_ONLY yükleme/boşaltma uygulanır. MMU_RECOVER otomatik durum kontrolünü; TOOL/GATE/LOADED parametreleri manuel düzeltmeyi sağlar. MMU_UNLOCK ve RESUME ayrı kalır. Eşleme MMU_TTG_MAP, gruplar MMU_ENDLESS_SPOOL üzerinden kaydedilir. Ayrıntılar kurulu sürüm ve donanıma göre doğrulanmalıdır.

Modelde tool, ttg_map, gate_material, action, operation, filament_pos, print_state, reason_for_pause, sensors, sync_drive ve bowden_progress gerekir. mmu_machine üzerinden sürüm ve ünite yetenekleri okunur. Alan yokluğu ile false/0 birbirine karıştırılmaz.

Kaynaklar: [komut referansı](https://moggieuk.github.io/Happy-Hare-Doc/Reference-Commands/), [durum değişkenleri](https://moggieuk.github.io/Happy-Hare-Doc/Reference-Printer-Variables/), [resmi ana panel kodu](https://github.com/moggieuk/KlipperScreen-Happy-Hare-Edition/blob/master/panels/mmu_main.py), [kurtarma kodu](https://github.com/moggieuk/KlipperScreen-Happy-Hare-Edition/blob/master/panels/mmu_recover.py).

## Uygulama sırası ve doğrulama
Önce MMU tam ekran yaşam döngüsü ve normalize edilmiş durum modeli; ardından ana ekran, kanallar, komut kilitleri ve kurtarma; sonra eşleme/EndlessSpool ve opsiyonel donanım.

Draw_Status_Area çağrısı bütün MMU ekranlarında bastırılmalı. Girişte tüm 480 piksel temizlenmeli, çıkışta ana ekran ve genel durum paneli yeniden çizilmeli. Bağlantı hatası/popup dönüşü aynı sahiplik kuralını korumalı.

Tüm ekranı sürekli yeniden çizmek yerine değişen alanlar güncellenmeli. Mevcut seri hızına uygun seyrek durum güncellemeleri ve olay odaklı odak çizimi önerilir; hedef yenileme hızı gerçek cihazda ölçülmeli.

Demoların metin sınırları kontrol edildi ve iki toplu PNG görsel olarak incelendi. Donanım, gerçek LCD fontları, seri hat performansı, gerçek yazıcıdaki komut güvenlik koşulları test edilmedi. Bu teslim tasarım çalışmasıdır; MMU implementasyonu henüz yapılmadı.


</details>
