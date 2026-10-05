# Regression contracts

Run from the repository root:

```sh
python3 -m unittest discover -s tests -v
```

The tests use Python's standard library. Import-time GPIO, serial, timer and
HTTP dependencies are replaced; no hardware or network connection is opened.
Real UI/backend methods run against isolated printer state and mocked I/O.

Known defects are marked `expectedFailure` until their implementation is fixed.
Each fix must remove its marker and pass the same contract. An unexpected pass
fails the suite, preventing fixed defects from silently remaining on this list.
Expected failures are known defects, not working features or release approval.

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
