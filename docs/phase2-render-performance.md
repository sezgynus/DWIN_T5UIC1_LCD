# Phase 2 render performance

Phase 2 reduces host-to-panel UART traffic without bypassing the
`T5UIC1Display` abstraction. Measurements use the real driver with a fake
serial transport and report complete DWIN frames, bytes, refresh commands and
host-side render duration.

## Baseline

| Workload | Packets | UART bytes | Refreshes |
| --- | ---: | ---: | ---: |
| Status dashboard full render | 24 | 379 | 1 |
| Prepare full render | 24 | 411 | 1 |
| Control full render | 18 | 295 | 1 |
| Print progress render | 5 | 69 | 1 |
| Print elapsed + remaining render | 3 | 46 | 1 |

Full renders remain unchanged so screen entry and reconnect behavior stay
deterministic.

## Optimized steady-state paths

- An unchanged status dashboard emits no UART frames and no refresh.
- A single changed dashboard value redraws only that value and one refresh.
- Unchanged print progress, elapsed minute and remaining minute emit no UART
  frames and no refresh.
- Prepare/Control encoder movement inside the current viewport redraws only the
  old and new cursor rectangles plus one refresh. A Prepare cursor move is
  therefore 3 packets instead of the 24-packet full menu render (87.5% fewer
  packets). Scrolling the viewport still performs a full render.

Render caches are UI-owned because only the UI knows whether previous pixels
are still valid. They are invalidated by UART epoch changes; print cache is
also reset when entering PrintProcess.

## Driver features deliberately not forced into use

- Refresh batching: measured logical workloads already issue one `0x3D`.
  The driver also suppresses an update when no drawing command made the frame
  dirty.
- Virtual-area static menu caching: both virtual areas participate in the
  managed atlas architecture. Swapping them for ordinary menu backgrounds
  would add `0x22/0x25` reload traffic and undermine atlas locality.
- Polyline batching: the bed-mesh grid consists of independent horizontal and
  vertical segments. Joining them into one polyline would draw unwanted
  connecting segments.
- Native numeric `0x14`: available through the driver, but changing existing
  text rendering has little measured traffic benefit compared with eliminating
  whole redraws and would require visual equivalence validation.
- Hardware animation `0x28/0x29`: the current UI has no host-driven frame
  animation loop to offload.
- SRAM/Picture/Data Flash: thumbnail SRAM caching and managed persistent atlas
  storage already cover the current repeated-image use cases.

The performance policy is therefore to eliminate redundant rendering first,
and only use additional panel-side mechanisms when a measured workload can
benefit without increasing cache churn or changing visual behavior.
