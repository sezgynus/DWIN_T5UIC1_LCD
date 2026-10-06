# Regression contracts

Run from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

The tests use Python's standard library. Import-time GPIO, serial, timer and
HTTP dependencies are replaced; no hardware or network connection is opened.
Real UI/backend methods run against isolated printer state and mocked I/O.

The original regression contracts now all pass without expected-failure markers.
Hardware and live-server validation are still separate from these isolated tests.

Initial coverage: resume routing, paused progress/duration, homing invalidation,
and hotend/bed target application through both Temperature and Tune menus.
Coverage now also includes transport reconnection, file-list changes,
coordinate/modal-state preservation and UART framing as described below.

Transport coverage now also checks optional authentication, timeout forwarding,
HTTP/JSON error handling, recovery on the next GET, observable POST results,
closed-client rejection and cancellation of pending commands after failure.
Resume routing and homing invalidation are fixed and no longer expected failures.

WebSocket coverage checks JSON-RPC identification, optional auth, available-object
subscriptions, partial snapshot merging, out-of-order updates, notifications
arriving before the subscription response, Klipper lifecycle changes, reconnect,
file-list invalidation and command rejection after a connection-epoch change.
The fake socket exercises the subscriber's real bootstrap/reconnect code; no
running Moonraker server or physical printer is required.

UI coverage checks concurrent producers, FIFO order, one thread for initialization,
events/ticks/cleanup, bounded queue overload, startup failures, exception recovery,
press debounce, stale connection events and deeply immutable printer snapshots.
An integration test runs real menu rendering and UART packet construction against
a fake serial port and confirms writes and close all occur on the UI owner.

Capability tests exercise all eight hotend/bed/fan combinations, compact menu
indices and scrolling, active extruder selection, effective heater/extrusion and
axis limits, reconnect replacement, invalid configuration rejection, atomic
preheat validation, fan percentage conversion and runtime offset routing.
Bootstrap now queries effective configfile settings before subscribing.

Preset coverage uses temporary directories: save/restart round trips, instance
isolation, corrupt and unsupported files, invalid numeric values, XDG defaults,
and failed atomic replacement preserving the old file and cleaning temporary
files. No user settings are written by these tests.

Jog coverage checks all coordinate/extrusion mode combinations, save/restore
without G92, displacement from command space, negative limits, homing, cold
and excessive extrusion, paused/printing rejection, numeric/axis validation,
Z velocity caps and local UI edits until confirmation. Actual motion and
Klipper error recovery still require live printer validation.

Print screen coverage checks paused startup/resume, completion confirmation and
acknowledgement, new-print reset, cancellation/standby, retained error messages,
external speed updates and editor isolation.

File coverage checks cached empty lists, path selection across insert/delete,
failed refresh blocking starts, path-based submission, duplicate suppression,
HTTP/status confirmation, failures/cancellation/epoch changes, timeout without
retry and snapshot-only scrolling.

Preheat fan tests check one combined submission, invalid fan values preventing
partial heating, optional devices, zero fan speed and active extruder selection.

Motion coverage checks all four Klipper parameters and commands, numeric domains,
missing/invalid-field omission, local edits until confirmation, cruise-ratio
boundaries and external status updates.

UART tests cover first-frame header/tail, fragmented ACK with noise, incomplete
ACK, bounded noise storage/retries, timeout and short-write cleanup, UART Read,
backlight validation and independent buffers. The existing UI ownership test
now exercises the single-write frame path. Firmware compatibility and display
rendering still require a physical panel.

UART recovery tests cover missing-panel retry timing, reconnect redraw without
printer commands, short-write disconnect handling, old-input rejection, closed
display rejection and unrelated error propagation.

Configuration coverage checks environment defaults, CLI overrides and invalid
pin/timeout rejection before GPIO imports. Unit syntax was checked with
systemd-analyze using the local Python executable substituted for the Pi-only
venv path; this does not replace target-Pi service lifecycle validation.

Probe coverage checks homing, active-session/config/print guards, start-result
and manual-state gating, owned TESTZ and serialization, accept plus pending
offset confirmation, abort without save, explicit save guards and epoch changes
without replay. No physical probing is performed.

Command feedback tests distinguish HTTP acceptance from expected printer state,
check errors/cancellation/epochs/timeouts, duplicate suppression, acknowledgement
without retry, validation failures and future-returning backend actions.

Packet tests cover the DWIN protocol: color-bearing points,
padded numeric text, scaled rounding, complete sign fields and invalid-input
isolation. No physical panel is exercised.

The packet fixtures also cover clear/line/rectangle/area movement, JPG
show/cache, QR and icon animation packets; decimal sign transitions retain a
complete field and numeric overflow draws explicit # markers. The existing real-menu fixture
runs the updated driver on the UI owner with a fake serial port. These fixtures
verify source-derived bytes and routing, not screen-side execution or rendering.

Final audit rendering coverage includes 100% progress, completed-minute time
formatting (including 100-hour prints), negative zero, immediate reconnect flush
and input-owner flush for early-returning editors. A01–A09 regressions cover GPIO
error acknowledgement, isolated offset editing, epoch/cache invalidation, jog
recovery, atomic packet validation and bounded numeric rendering. The limits of
these isolated fixtures are listed in docs/source-audit.md.

Screws tilt coverage checks optional Prepare menu discovery, geometry-based corner
placement, conditional homing, print/manual-probe/recovery rejection, completed
WebSocket RPCs followed by fresh result queries, identical repeated measurements,
malformed/incomplete results, largest-turn recommendation, 0.05 mm peak-to-peak
tolerance, minute rollover, epoch/disconnect/timeout failures, encoder locking,
Continue/back navigation and corner label bounds. Completion RPC tests also check
notification merging, response IDs, command errors, disconnect and cancelled queues.

Physical check: open Prepare → Screws Tilt Adjust → Calculate, compare Base and
every direction/amount with the Moonraker console, turn the indicated screw and
repeat. Check input is ignored while probing, Continue returns to Calculate,
missing homing runs first, and all labels fit on the actual panel.

Bed mesh coverage checks completion-tracked calibration and fresh result queries,
conditional homing, duplicate/mutually exclusive calibration guards, profile
selection without LOAD, malformed/empty/deleted profiles, raw probe sample
mapping with XY offsets, repeated samples and measurements, config ownership
and exact pending-profile validation before SAVE_CONFIG, explicit stop/save
confirmations, interruption and timeout handling. UI tests cover grid orientation,
color/radius scaling, bounded labels through 25×25, profile-list scrolling,
real UART result/menu packets and reconnect redraw without command replay.

Physical bed mesh checks:

- Open Home → Leveling → Bed Mesh Calibrate and compare the final point values and
  min/max with Moonraker's bed_mesh.probed_matrix.
- Check raw probe progress, circle colors/sizes and labels on the physical LCD.
- Continue, then repeat calibration; the owned pending profile must not block it.
- Open Home → Leveling → Mesh Viewer, select saved profiles and Current Mesh, and verify
  that viewing does not change bed_mesh.profile_name or move the printer.
- Save only after the displayed profile/restart confirmation; after restart,
  verify the new lcd_mesh_N profile persists and matches the measured matrix.
- If testing Cancel, confirm Stop only when a Klipper shutdown is intended;
  restore operation with FIRMWARE_RESTART afterward.

These isolated tests do not verify physical probing, LCD appearance, service
lifecycle or live-server persistence.

Home navigation regressions cover four-icon paging, forward/reverse page boundaries,
empty-slot rejection, Leveling, MMU and Info routing, return to the originating Home
page or Control menu, capability removal and preservation of the MMU/dashboard
areas while paging.

Bed Mesh menu regressions check that Prepare/Control no longer duplicate its
entries, the Home shortcut opens a submenu without starting motion, calibration
and profile-list Back/Continue return to that menu, viewer-only access without a
probe, bounded menu selection and UART reconnect without measurement replay.

MMU placeholder regressions verify Back-only navigation with and without bed mesh,
return to the same Home selection, no G-code on entry/exit and bounded reel icon
rendering with distinct selected/unselected colors.

File sorting regressions cover saved Mainsail name/date/size preferences in both
directions, newest-first fallback, malformed timestamps/settings, bounded polling,
cached file lists, selected-path preservation and stale Enter rejection on resort.

Directory browsing regressions cover empty folders, nested entry/parent Back,
folder-first sorting in both directions at each level, cached resorting, basename
labels and folder icons, full-path print submission, deleted files/directories,
stale Enter rejection and invalid path/entry validation.

Thumbnail preview regressions cover RGB565 runs, 80×80 aspect-preserving
conversion, transparency and decode limits, authenticated bounded downloads,
relative thumbnail paths, confirmation before Print, Cancel/late-result handling,
incremental rendering bounds, redraw, file/epoch revalidation and duplicate starts.
Physical image quality and UART drawing latency still require LCD testing.
