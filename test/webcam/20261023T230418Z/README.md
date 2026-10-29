# Webcam MJPEG capture

120 consecutive original JPEG frames from the Logitech Webcam C930e at
1920 x 1080, nominal 30 fps. The first 30 startup frames were discarded.
Camera settings were queried and left unchanged. No image re-encoding was used.

- `frame_000000.jpg` through `frame_000119.jpg`: exact V4L2 buffer contents.
- `capture.mjpg`: concatenation of those frame buffers.
- `manifest.json`: driver sequence numbers, monotonic timestamps, byte offsets, sizes, and SHA-256 hashes.
- `device.txt`: settings at capture time.
- `capture-command.json` and `capture.log`: command and capture diagnostics.

All 120 frames decoded without warnings using the optimized libjpeg-turbo
build in `/tmp/mjpeg-release`. Byte counts were matched against the V4L2
log before splitting; concatenating the JPEG files reconstructs the raw stream.

Example decode benchmark from the repository root:

```sh
/tmp/mjpeg-release/tjbench-static test/webcam/20261023T230418Z/frame_000060.jpg -nowrite -warmup 1 -benchtime 5
```
