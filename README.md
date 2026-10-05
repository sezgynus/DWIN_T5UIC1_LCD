# DWIN_T5UIC1_LCD

Python UI for the Ender 3 V2 DWIN T5UIC1 panel, using
[Klipper](https://www.klipper3d.org/) and
[Moonraker](https://github.com/Arksine/moonraker).

### UART preparation

In `sudo raspi-config`, disable the serial login console and enable serial
hardware, then reboot. Select the UART routed to the display's GPIO14/15 pins
for your Pi model; do not assume ttyAMA0 or serial0 always uses those pins.
See the [official Raspberry Pi UART documentation](https://www.raspberrypi.com/documentation/computers/configuration.html#configuring-uarts).
Bluetooth overlays and boot configuration paths are model/OS dependent; this
project does not require one universal overlay.

### Moonraker connection (refactor branch)

The LCD connects to Moonraker over HTTP and WebSocket; no direct Klipper socket path or
OctoPrint compatibility endpoint is required. The default URL is
`http://127.0.0.1:7125`. If using a reverse proxy, set its URL explicitly:

```sh
python3 run.py --moonraker-url http://127.0.0.1:80 --request-timeout 5
```

`MOONRAKER_URL` can supply the URL. For installations requiring an API key,
provide `MOONRAKER_API_KEY` in the process environment. Empty keys are not sent.
Do not commit credentials or disable Moonraker authorization.

`--serial-port`, `--encoder-pins A B`, and `--button-pin` configure hardware.
The current pin defaults preserve the existing run.py wiring (21/19 and 13);
set 26/19 explicitly if following the older wiring diagram below.

Commands execute on a dedicated serial worker and expose their result through
Futures. HTTP failures, invalid JSON and timeouts are checked. Failed commands
are never replayed; pending dependent commands are discarded. The LCD displays
a generic failure message and logs the error. The WebSocket subscriber reconnects after
connection failure without restarting the application; offline input is ignored.
A timed-out command may already have executed: inspect printer state before
issuing it again.

Status uses JSON-RPC at `/websocket`: client identification, printer object
list discovery and subscriptions. Only existing objects are subscribed. Partial
notifications merge into the initial snapshot; older notifications cannot replace
newer data. Klipper shutdown/restart/disconnect discards the old snapshot and
triggers a new discovery/subscription. Ping/pong checks detect silent disconnects.
Queued HTTP commands retain their connection epoch and are rejected if the
printer reconnects before execution. Already executing commands cannot be undone.

Install the refactor dependencies in a virtual environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py --moonraker-url http://127.0.0.1:7125
```

UI initialization, menu handlers, periodic rendering and cleanup now run on
one owner thread. GPIO callbacks enqueue immutable rotation/press events; they
never write to the display. Presses use edge events and capture-time debounce;
rotation counts are preserved rather than sampled and dropped by a rate limiter.
The bounded queue rejects overload and logs dropped input. Events from a previous
printer connection are discarded.

`PrinterData.state` is the immutable authoritative status snapshot. Existing HMI
edit values remain separate compatibility fields; editing them cannot change the
snapshot. Menu selection objects belong to each display instance.

`run.py` waits for the UI owner and handles SIGTERM/KeyboardInterrupt cleanup.
When constructing `DWIN_LCD` directly, call `display.wait()` to keep the process
running and `display.lcdExit()` to stop it.

Device menus now follow Klipper's discovered objects. Hotend, heated bed and part
fan rows are independently optional; heater fans do not count as part fans.
Effective `configfile.settings` supplies heater and extrusion limits, including
Klipper defaults. Toolhead status supplies physical axis limits and the active
extruder; temperature commands address that heater by name. Missing or invalid
required configuration blocks readiness rather than inventing limits.
Zero temperature means off; nonzero targets must fit the configured range.
Preheat validates all installed heater targets before submitting a script.
Fan edits use percentages and convert to Klipper's M106 scale.

Probe and bed mesh availability are detected, but the calibration wizard is not
implemented yet. The Z-offset menu changes the runtime G-code offset only.
Temperature and Tune confirmations now submit the corresponding live heater
target; preset editors only change preset values. Paused and terminal jobs retain
progress and elapsed print duration. Completion follows `print_stats.state`,
so a rounded progress value cannot mark a running job complete.
File selection uses a sorted, cached path snapshot, refreshed after file-list
notifications. Inserting/reordering files preserves the selected path; deletion
returns the cursor to Back. An empty list is cached too. List-fetch errors keep
the old view but block starts until a valid refresh succeeds.
Print start sends the selected path, blocks duplicate presses, and waits for both
the HTTP result and subscribed print state before opening the print screen.
Failure, cancellation, connection-epoch changes or an unconfirmed start after
30 seconds show an acknowledgement message; start commands are never retried
automatically. A late successful start can still occur after a timeout: check
printer state before submitting again. File listing remains a bounded HTTP GET
on menu entry/notification refresh; rendering and encoder navigation use only
the cached snapshot.

Print screen selection handles paused startup, completion, cancellation and
print errors explicitly. Completion stays on the print screen until Enter;
acknowledging it does not reset the printer's speed. Print error messages remain
visible until Enter. A new print clears the old completion prompt.
The displayed speed percentage follows subscribed `gcode_move.speed_factor`,
including edits from other clients; an open speed editor keeps its local target.
M220 submission does not change the reported value until status confirms it.

The Save row persists both PLA/ABS profiles (heater targets and fan percentage)
to `$XDG_CONFIG_HOME/dwin-lcd/presets.json`, or `~/.config/dwin-lcd/presets.json`
when XDG_CONFIG_HOME is unset. Use `--settings-file /absolute/path/presets.json`
to override it, including in a systemd unit. The service user must be able to write
the parent directory. Edits remain in memory until Save is selected.
The versioned file is validated before loading; missing files use defaults and
invalid files are logged and preserved. Writes use a flushed temporary file and
atomic replacement; failed saves return failure to the menu's audio feedback.
Loading presets never sends heater commands. Applying a profile validates all
installed heater targets and the available part fan's percentage before sending
one script. The script sets the bed, active hotend and preset fan speed; absent
devices are skipped. Validation prevents partial submission, but the script is
not a transaction if Klipper rejects a command while executing it.

Jog targets use `gcode_move.position` (command space before transforms), not
G-code coordinates shifted by G92 or runtime offsets. Each jog saves Klipper's
G-code state, performs a relative displacement with explicit extrusion/feed
factors, then restores state with `MOVE=0`. It does not reset the work origin or
move back to the starting point. XYZ requires the selected axis to be homed and
its target inside discovered bounds. Extrusion requires `can_extrude` and the
configured maximum extrusion distance. Jogging during printing/paused jobs is
rejected; feed is capped by toolhead velocity and configured Z velocity.
Encoder edits remain local until confirmation; position follows status updates.

The command sequence is not a transaction: if Klipper rejects a movement, later
commands (including restore) may not execute. Transport failures are surfaced
and queued commands are cancelled; inspect printer state before continuing after
a movement error. Bed mesh and other transforms remain under Klipper's checks.
The save/restore semantics were checked against [Klipper gcode_move.py](https://github.com/Klipper3d/klipper/blob/461c4e3722c3a897fba1c6b3f0780a5315043842/klippy/extras/gcode_move.py).

The Motion menu edits Klipper runtime `max_velocity`, `max_accel`,
`square_corner_velocity` and `minimum_cruise_ratio` using `SET_VELOCITY_LIMIT`.
Values come from subscribed toolhead status; unsupported or invalid fields are
omitted. Encoder increments are 1 mm/s, 10 mm/s², 0.1 mm/s and 0.01 respectively.
Edits stay local until Enter; reported values change only when status confirms
them. Numeric domains follow [Klipper toolhead.py](https://github.com/Klipper3d/klipper/blob/461c4e3722c3a897fba1c6b3f0780a5315043842/klippy/toolhead.py).
SCV is not Marlin jerk. These values are runtime changes; the menu does not send
SAVE_CONFIG or promise persistence. Steps/mm and rotation-distance calibration
are outside this menu; it does not create per-axis Marlin-style limits.

UART startup now sends the first handshake with the AA header and frame tail.
The incremental ACK reader accepts the existing `AA 00 O K` signature across
split reads and discards noise without an unbounded buffer. The default is three
handshake attempts of one second each; failure closes the port and raises an
error rather than blocking startup forever. The driver constructor accepts
`handshake_timeout` and `handshake_attempts` overrides.
Frames are sent in one serial write with a write timeout. Short writes/errors
close the port and are not automatically retried. `Read` uses UART; backlight
accepts byte values and retains the previous intended minimum of 0x1F.
These tests verify the existing packet contract, not every panel firmware's
instruction set. The UI tolerates a missing panel at startup and keeps updating printer status.
It retries UART on the UI owner after at least five seconds (on the next tick),
using one bounded handshake attempt. On reconnect it reloads language assets and
redraws the current print/main/error screen; local editors are exited. Inputs
captured before the UART connection change are discarded. Reconnection only
restores display state and never replays printer commands. Physical panel
validation remains outstanding.

### Install on Raspberry Pi OS

Use Python 3.11 or newer. The systemd unit below uses `/opt/dwin-lcd`.

```sh
sudo apt update
sudo apt install git python3-venv python3-dev build-essential
sudo git clone --branch refactor/modern-klipper-moonraker https://github.com/sezgynus/DWIN_T5UIC1_LCD.git /opt/dwin-lcd
sudo python3 -m venv /opt/dwin-lcd/.venv
sudo /opt/dwin-lcd/.venv/bin/python -m pip install -r /opt/dwin-lcd/requirements.txt
```

The manifest includes GPIOZero, lgpio, pyserial and websocket-client. HTTP uses
the Python standard library. Installation needs access to the Python package
index; actual GPIO/UART operation requires a supported Pi and device permissions.

### Wire the display 
  * Display <-> Raspberry Pi GPIO BCM
  * Rx  =   GPIO14  (Tx)
  * Tx  =   GPIO15  (Rx)
  * Ent =   GPIO13
  * Encoder A/B = GPIO21 / GPIO19 by default (`--encoder-pins 21 19`)
  * Older GPIO26/19 wiring: use `--encoder-pins 26 19`; reverse the pair if needed
  * Vcc =   2   (5v)
  * Gnd =   6   (GND)

Here's a diagram based on my color selection:

<img src ="images/GPIO.png?raw=true" width="325" height="75">
<img src ="images/panel.png?raw=true" width="325" height="180">

I tried to take some images to help out with this: You don't have to use the color of wiring that I used:

<img src ="images/wire1.png?raw=true" width="200" height="400"> <img src ="images/wire2.png?raw=true" width="200" height="400">

<img src ="images/wire3.png?raw=true" width="400" height="200">

<img src ="images/wire4.png?raw=true" width="400" height="300">

### Run manually

Use the existing `run.py`; no source edit or embedded API key is needed:

```sh
cd /opt/dwin-lcd
.venv/bin/python run.py --serial-port /dev/ttyAMA0 --encoder-pins 21 19 --button-pin 13
```

Verify the port and BCM pin numbers for your wiring. The invoking user needs
access to the UART and gpiochip devices. Default presets are stored under that
user's XDG configuration directory. `--help` works without importing GPIO code.

### Run at boot

The supplied service uses a dedicated account and the install path above:

```sh
id -u dwinlcd >/dev/null 2>&1 || sudo useradd --system --user-group --home-dir /var/lib/dwin-lcd --no-create-home --shell /usr/sbin/nologin dwinlcd
getent group dialout gpio
sudo install -m 0600 /opt/dwin-lcd/dwin-lcd.env.example /etc/default/dwin-lcd
sudoedit /etc/default/dwin-lcd
sudo install -m 0644 /opt/dwin-lcd/simpleLCD.service /etc/systemd/system/simpleLCD.service
sudo systemctl daemon-reload
sudo systemctl enable --now simpleLCD.service
sudo journalctl -u simpleLCD.service -f
```

The `dialout` and `gpio` groups must exist and grant access to your actual UART
and gpiochip devices. Adapt `SupplementaryGroups` to the installed OS if needed.
`StateDirectory=dwin-lcd` creates `/var/lib/dwin-lcd` owned by the service user.
The root-owned environment file can hold an optional API key; do not commit it.
CLI arguments override environment defaults:

| Environment variable | CLI option | Default |
|---|---|---|
| MOONRAKER_URL | --moonraker-url | http://127.0.0.1:7125 |
| MOONRAKER_API_KEY | Environment only | Empty |
| DWIN_REQUEST_TIMEOUT | --request-timeout | 5 seconds |
| DWIN_SERIAL_PORT | --serial-port | /dev/ttyAMA0 |
| DWIN_ENCODER_PINS | --encoder-pins A B | 21 19 (BCM) |
| DWIN_BUTTON_PIN | --button-pin | 13 (BCM) |
| DWIN_SETTINGS_FILE | --settings-file | User XDG path; service uses /var/lib/dwin-lcd/presets.json |

Restart after environment-file edits. The unit starts without a fixed sleep or
hard dependency on a local Moonraker service; application reconnect handles
late startup. `Restart=on-failure` handles crashes with a five-second delay and
rate limit. An intentional stop stays stopped. SIGTERM uses application cleanup;
systemd enforces a 15-second stop limit. Logs go to journald.

```sh
sudo systemctl restart simpleLCD.service
sudo systemctl stop simpleLCD.service
sudo systemctl status simpleLCD.service
```

### Validation and remaining work

```sh
cd /opt/dwin-lcd
.venv/bin/python -m unittest discover -s tests -v
```

The isolated tests do not prove physical motion or panel compatibility. Probe
calibration wizard, full panel instruction-set verification and final hardware
validation remain outstanding. The supplied systemd service must still be
validated with start/stop/restart and device permissions on the target Pi.
