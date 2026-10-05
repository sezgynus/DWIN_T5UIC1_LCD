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
