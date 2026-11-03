# Enumerate and capture camera MJPEG modes

Agent-side camera access remains blocked because the sandbox exposes no
/dev/video nodes. `environment.json` records the initial observation. The user
subsequently captured both cameras from the host terminal: 119 Logitech C930e
modes and 60 Microsoft LifeCam Studio modes, totaling 2,148 frames.
[Validation and performance results](../nv12/multi-camera/README.md) cover the
actual dumps, including dimensions, restart intervals and camera restoration.
The earlier 1920x1080 capture from 20261023 remains unchanged.

Run from the host Linux terminal:

```sh
python3 /home/al/src/libjpeg-turbo/test/webcam/mjpeg-modes/capture.py
```

The script uses installed `v4l2-ctl` and Python's standard library. It:

- Saves the actual `--list-formats-ext` output and all distinct discrete MJPG
  resolution/frame-rate pairs. Other formats are excluded. Any stepwise or
  continuous modes are recorded as unhandled rather than guessed.
- Saves initial device state, format and frame rate before making changes.
- Requests each advertised MJPG mode, records the negotiated settings,
  discards 30 startup frames, and captures 12 frames per mode by default.
- Saves raw `capture.mjpg`, original per-buffer JPEGs, logs, sequence numbers,
  monotonic timestamps, byte offsets and SHA-256 hashes. Buffer lengths come
  from the driver log and must exactly reconstruct the stream; no splitting
  by naive JPEG signature search or image re-encoding is used.
- Inspects each JPEG header for dimensions, precision, component sampling,
  table selectors, DRI and DHT/DQT segment hashes. This is header inspection,
  not decoder correctness validation. Tables after the first scan are outside
  the header summary. Requested and negotiated frame rates remain distinct;
  exposure can affect observed frame timing.
- Attempts to restore the original format and nominal frame rate in a finally
  block and records whether restoration was verified. Camera controls are not
  changed. Capture failures are recorded and raw partial data retained.

Output goes under ignored `captures/YYYYMMDDTHHMMSSZ/`, with one folder per
mode. `modes.json`, `summary.json`, and each mode's `manifest.json` provide the
inventory for subsequent geometry-aware NV12 validation. Current optimization
runners hardcode 1920x1080 4:2:2; do not use them directly on arbitrary new
resolutions or sampling factors.

Options:

```sh
# Read-only inventory, without streaming or mode changes:
python3 test/webcam/mjpeg-modes/capture.py --list-only
# More temporal samples, alternate video capture node:
python3 test/webcam/mjpeg-modes/capture.py --device /dev/video0 --frames 30
```

Each invocation creates a fresh directory and refuses to overwrite an existing
output directory. Raw captures remain local and ignored. Timings for decoding
or encoder throughput are not collected by this script.

`check.py` verified reconstruction of all 120 original capture buffers and
hashes, the format parser, simulated raw capture and restoration after both
successful and failed capture. This does not substitute for a hardware run.
