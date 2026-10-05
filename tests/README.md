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
Transport reconnection, file-list changes, coordinate/modal-state preservation
and UART framing need dedicated fixtures as those interfaces are refactored.

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

Packet tests follow the pinned mriscoc DWIN/ProUI reference: color-bearing points,
padded numeric text, scaled rounding, complete sign fields and invalid-input
isolation. No physical panel is exercised.

The pinned Marlin fixtures also cover clear/line/rectangle/area movement, JPG
show/cache, QR and icon animation packets; decimal sign transitions retain a
complete field and rounding overflow is rejected. The existing real-menu fixture
runs the updated driver on the UI owner with a fake serial port. These fixtures
verify source-derived bytes and routing, not screen-side execution or rendering.

Final audit rendering coverage includes 100% progress, completed-minute time
formatting (including 100-hour prints), negative zero, immediate reconnect flush
and input-owner flush for early-returning editors. Remaining findings and the
limits of these isolated fixtures are listed in docs/source-audit.md.
