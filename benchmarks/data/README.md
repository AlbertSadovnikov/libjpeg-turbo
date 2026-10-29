# Embedded webcam fixture

`webcam_1920x1080_422.jpg` is an exact copy of
`test/webcam/20261023T230418Z/frame_000060.jpg`, captured from the Logitech
Webcam C930e on 2026-10-23. It is not re-encoded.

- 1920 x 1080, 8-bit interleaved sequential YCbCr JPEG, 4:2:2 subsampling.
- No restart interval; 371,718 bytes.
- SHA-256: `c55c3d3ff712f3cbbeeef02b04af9cb460b555770614ba0b08b90b1424bf7d91`.

This copy makes the suite independent of the original capture directory.
The build converts it into an aligned constant byte array in the executable.
The JPEG file is only needed while building; no frame file is opened at runtime.
