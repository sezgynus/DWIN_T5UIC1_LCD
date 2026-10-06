# Historical source audit — 2026-10-05

This document records an earlier source review and its closed findings. It is
**not the current feature list or a claim of complete hardware validation**.
For v1.0.0 functionality and current limits, see [README](../README.md) and
[README_TR](../README_TR.md). For current software checks, see
[test contracts](../tests/README.md).

## Scope at the time

The review covered display framing/rendering, input ownership, command/error
handling, movement recovery, state epochs, configuration and asset coordinates.
It used source inspection and fake serial/HTTP/GPIO I/O; no physical printer,
LCD or Pi service was exercised by that audit. Its isolated suite contained
187 passing tests at that time; that number is historical, not today's total.

## Closed findings

The original finding IDs and commit references are retained below.

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
| A09 | Sayısal taşma exception yerine alan genişliğinde # işareti çiziyor; gerçek hedef değişmiyor. İşaret geçişleri alanı temizliyor, Motion değerleri gerektiğinde tam bilimsel gösterim kullanıyor. | 2026-10-05 audit commit |


The audit also corrected the three-digit 100% field, completed-minute duration
formatting, negative-zero rendering and immediate screen flushing after input
or reconnect. Moves and edit targets use `gcode_move.position` consistently.

## Limits and later changes

- Jog recovery protects this LCD client; it does not lock other Moonraker clients.
  Its recovery state lives in process memory. An unsuccessful state restore does
  not clear the movement guard.
- Asset hashes describe the audited files, not every installed panel. Real UART
  timing, fonts, filtering and visual placement require physical checks.
- The audit predates the current calibration, paged Home, folder browser,
  metadata preview and SRAM/JPEG cache features. Its earlier absence of image
  transfer APIs is no longer a current limitation.
- Later user panel tests exercised preview display, caching and metadata layout;
  they do not establish compatibility across every printer/display configuration.

Git history retains the full earlier report and implementation details.
