# Huffman codes: webcam_1920x1080_422.jpg

## DC table 0: 12 codes

Counts for lengths 1..16: 0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0

| Code | Length | Symbol | Meaning |
|---|---:|---|---|
| `00` | 2 | `0x00` | Read 0 DC difference bits |
| `010` | 3 | `0x01` | Read 1 DC difference bits |
| `011` | 3 | `0x02` | Read 2 DC difference bits |
| `100` | 3 | `0x03` | Read 3 DC difference bits |
| `101` | 3 | `0x04` | Read 4 DC difference bits |
| `110` | 3 | `0x05` | Read 5 DC difference bits |
| `1110` | 4 | `0x06` | Read 6 DC difference bits |
| `11110` | 5 | `0x07` | Read 7 DC difference bits |
| `111110` | 6 | `0x08` | Read 8 DC difference bits |
| `1111110` | 7 | `0x09` | Read 9 DC difference bits |
| `11111110` | 8 | `0x0A` | Read 10 DC difference bits |
| `111111110` | 9 | `0x0B` | Read 11 DC difference bits |

## AC table 0: 162 codes

Counts for lengths 1..16: 0, 2, 1, 3, 3, 2, 4, 3, 5, 5, 4, 4, 0, 0, 1, 125

| Code | Length | Symbol | Meaning |
|---|---:|---|---|
| `00` | 2 | `0x01` | Skip 0 zeros, read 1 value bits |
| `01` | 2 | `0x02` | Skip 0 zeros, read 2 value bits |
| `100` | 3 | `0x03` | Skip 0 zeros, read 3 value bits |
| `1010` | 4 | `0x00` | End of block |
| `1011` | 4 | `0x04` | Skip 0 zeros, read 4 value bits |
| `1100` | 4 | `0x11` | Skip 1 zeros, read 1 value bits |
| `11010` | 5 | `0x05` | Skip 0 zeros, read 5 value bits |
| `11011` | 5 | `0x12` | Skip 1 zeros, read 2 value bits |
| `11100` | 5 | `0x21` | Skip 2 zeros, read 1 value bits |
| `111010` | 6 | `0x31` | Skip 3 zeros, read 1 value bits |
| `111011` | 6 | `0x41` | Skip 4 zeros, read 1 value bits |
| `1111000` | 7 | `0x06` | Skip 0 zeros, read 6 value bits |
| `1111001` | 7 | `0x13` | Skip 1 zeros, read 3 value bits |
| `1111010` | 7 | `0x51` | Skip 5 zeros, read 1 value bits |
| `1111011` | 7 | `0x61` | Skip 6 zeros, read 1 value bits |
| `11111000` | 8 | `0x07` | Skip 0 zeros, read 7 value bits |
| `11111001` | 8 | `0x22` | Skip 2 zeros, read 2 value bits |
| `11111010` | 8 | `0x71` | Skip 7 zeros, read 1 value bits |
| `111110110` | 9 | `0x14` | Skip 1 zeros, read 4 value bits |
| `111110111` | 9 | `0x32` | Skip 3 zeros, read 2 value bits |
| `111111000` | 9 | `0x81` | Skip 8 zeros, read 1 value bits |
| `111111001` | 9 | `0x91` | Skip 9 zeros, read 1 value bits |
| `111111010` | 9 | `0xA1` | Skip 10 zeros, read 1 value bits |
| `1111110110` | 10 | `0x08` | Skip 0 zeros, read 8 value bits |
| `1111110111` | 10 | `0x23` | Skip 2 zeros, read 3 value bits |
| `1111111000` | 10 | `0x42` | Skip 4 zeros, read 2 value bits |
| `1111111001` | 10 | `0xB1` | Skip 11 zeros, read 1 value bits |
| `1111111010` | 10 | `0xC1` | Skip 12 zeros, read 1 value bits |
| `11111110110` | 11 | `0x15` | Skip 1 zeros, read 5 value bits |
| `11111110111` | 11 | `0x52` | Skip 5 zeros, read 2 value bits |
| `11111111000` | 11 | `0xD1` | Skip 13 zeros, read 1 value bits |
| `11111111001` | 11 | `0xF0` | Skip 16 zeros |
| `111111110100` | 12 | `0x24` | Skip 2 zeros, read 4 value bits |
| `111111110101` | 12 | `0x33` | Skip 3 zeros, read 3 value bits |
| `111111110110` | 12 | `0x62` | Skip 6 zeros, read 2 value bits |
| `111111110111` | 12 | `0x72` | Skip 7 zeros, read 2 value bits |
| `111111111000000` | 15 | `0x82` | Skip 8 zeros, read 2 value bits |
| `1111111110000010` | 16 | `0x09` | Skip 0 zeros, read 9 value bits |
| `1111111110000011` | 16 | `0x0A` | Skip 0 zeros, read 10 value bits |
| `1111111110000100` | 16 | `0x16` | Skip 1 zeros, read 6 value bits |
| `1111111110000101` | 16 | `0x17` | Skip 1 zeros, read 7 value bits |
| `1111111110000110` | 16 | `0x18` | Skip 1 zeros, read 8 value bits |
| `1111111110000111` | 16 | `0x19` | Skip 1 zeros, read 9 value bits |
| `1111111110001000` | 16 | `0x1A` | Skip 1 zeros, read 10 value bits |
| `1111111110001001` | 16 | `0x25` | Skip 2 zeros, read 5 value bits |
| `1111111110001010` | 16 | `0x26` | Skip 2 zeros, read 6 value bits |
| `1111111110001011` | 16 | `0x27` | Skip 2 zeros, read 7 value bits |
| `1111111110001100` | 16 | `0x28` | Skip 2 zeros, read 8 value bits |
| `1111111110001101` | 16 | `0x29` | Skip 2 zeros, read 9 value bits |
| `1111111110001110` | 16 | `0x2A` | Skip 2 zeros, read 10 value bits |
| `1111111110001111` | 16 | `0x34` | Skip 3 zeros, read 4 value bits |
| `1111111110010000` | 16 | `0x35` | Skip 3 zeros, read 5 value bits |
| `1111111110010001` | 16 | `0x36` | Skip 3 zeros, read 6 value bits |
| `1111111110010010` | 16 | `0x37` | Skip 3 zeros, read 7 value bits |
| `1111111110010011` | 16 | `0x38` | Skip 3 zeros, read 8 value bits |
| `1111111110010100` | 16 | `0x39` | Skip 3 zeros, read 9 value bits |
| `1111111110010101` | 16 | `0x3A` | Skip 3 zeros, read 10 value bits |
| `1111111110010110` | 16 | `0x43` | Skip 4 zeros, read 3 value bits |
| `1111111110010111` | 16 | `0x44` | Skip 4 zeros, read 4 value bits |
| `1111111110011000` | 16 | `0x45` | Skip 4 zeros, read 5 value bits |
| `1111111110011001` | 16 | `0x46` | Skip 4 zeros, read 6 value bits |
| `1111111110011010` | 16 | `0x47` | Skip 4 zeros, read 7 value bits |
| `1111111110011011` | 16 | `0x48` | Skip 4 zeros, read 8 value bits |
| `1111111110011100` | 16 | `0x49` | Skip 4 zeros, read 9 value bits |
| `1111111110011101` | 16 | `0x4A` | Skip 4 zeros, read 10 value bits |
| `1111111110011110` | 16 | `0x53` | Skip 5 zeros, read 3 value bits |
| `1111111110011111` | 16 | `0x54` | Skip 5 zeros, read 4 value bits |
| `1111111110100000` | 16 | `0x55` | Skip 5 zeros, read 5 value bits |
| `1111111110100001` | 16 | `0x56` | Skip 5 zeros, read 6 value bits |
| `1111111110100010` | 16 | `0x57` | Skip 5 zeros, read 7 value bits |
| `1111111110100011` | 16 | `0x58` | Skip 5 zeros, read 8 value bits |
| `1111111110100100` | 16 | `0x59` | Skip 5 zeros, read 9 value bits |
| `1111111110100101` | 16 | `0x5A` | Skip 5 zeros, read 10 value bits |
| `1111111110100110` | 16 | `0x63` | Skip 6 zeros, read 3 value bits |
| `1111111110100111` | 16 | `0x64` | Skip 6 zeros, read 4 value bits |
| `1111111110101000` | 16 | `0x65` | Skip 6 zeros, read 5 value bits |
| `1111111110101001` | 16 | `0x66` | Skip 6 zeros, read 6 value bits |
| `1111111110101010` | 16 | `0x67` | Skip 6 zeros, read 7 value bits |
| `1111111110101011` | 16 | `0x68` | Skip 6 zeros, read 8 value bits |
| `1111111110101100` | 16 | `0x69` | Skip 6 zeros, read 9 value bits |
| `1111111110101101` | 16 | `0x6A` | Skip 6 zeros, read 10 value bits |
| `1111111110101110` | 16 | `0x73` | Skip 7 zeros, read 3 value bits |
| `1111111110101111` | 16 | `0x74` | Skip 7 zeros, read 4 value bits |
| `1111111110110000` | 16 | `0x75` | Skip 7 zeros, read 5 value bits |
| `1111111110110001` | 16 | `0x76` | Skip 7 zeros, read 6 value bits |
| `1111111110110010` | 16 | `0x77` | Skip 7 zeros, read 7 value bits |
| `1111111110110011` | 16 | `0x78` | Skip 7 zeros, read 8 value bits |
| `1111111110110100` | 16 | `0x79` | Skip 7 zeros, read 9 value bits |
| `1111111110110101` | 16 | `0x7A` | Skip 7 zeros, read 10 value bits |
| `1111111110110110` | 16 | `0x83` | Skip 8 zeros, read 3 value bits |
| `1111111110110111` | 16 | `0x84` | Skip 8 zeros, read 4 value bits |
| `1111111110111000` | 16 | `0x85` | Skip 8 zeros, read 5 value bits |
| `1111111110111001` | 16 | `0x86` | Skip 8 zeros, read 6 value bits |
| `1111111110111010` | 16 | `0x87` | Skip 8 zeros, read 7 value bits |
| `1111111110111011` | 16 | `0x88` | Skip 8 zeros, read 8 value bits |
| `1111111110111100` | 16 | `0x89` | Skip 8 zeros, read 9 value bits |
| `1111111110111101` | 16 | `0x8A` | Skip 8 zeros, read 10 value bits |
| `1111111110111110` | 16 | `0x92` | Skip 9 zeros, read 2 value bits |
| `1111111110111111` | 16 | `0x93` | Skip 9 zeros, read 3 value bits |
| `1111111111000000` | 16 | `0x94` | Skip 9 zeros, read 4 value bits |
| `1111111111000001` | 16 | `0x95` | Skip 9 zeros, read 5 value bits |
| `1111111111000010` | 16 | `0x96` | Skip 9 zeros, read 6 value bits |
| `1111111111000011` | 16 | `0x97` | Skip 9 zeros, read 7 value bits |
| `1111111111000100` | 16 | `0x98` | Skip 9 zeros, read 8 value bits |
| `1111111111000101` | 16 | `0x99` | Skip 9 zeros, read 9 value bits |
| `1111111111000110` | 16 | `0x9A` | Skip 9 zeros, read 10 value bits |
| `1111111111000111` | 16 | `0xA2` | Skip 10 zeros, read 2 value bits |
| `1111111111001000` | 16 | `0xA3` | Skip 10 zeros, read 3 value bits |
| `1111111111001001` | 16 | `0xA4` | Skip 10 zeros, read 4 value bits |
| `1111111111001010` | 16 | `0xA5` | Skip 10 zeros, read 5 value bits |
| `1111111111001011` | 16 | `0xA6` | Skip 10 zeros, read 6 value bits |
| `1111111111001100` | 16 | `0xA7` | Skip 10 zeros, read 7 value bits |
| `1111111111001101` | 16 | `0xA8` | Skip 10 zeros, read 8 value bits |
| `1111111111001110` | 16 | `0xA9` | Skip 10 zeros, read 9 value bits |
| `1111111111001111` | 16 | `0xAA` | Skip 10 zeros, read 10 value bits |
| `1111111111010000` | 16 | `0xB2` | Skip 11 zeros, read 2 value bits |
| `1111111111010001` | 16 | `0xB3` | Skip 11 zeros, read 3 value bits |
| `1111111111010010` | 16 | `0xB4` | Skip 11 zeros, read 4 value bits |
| `1111111111010011` | 16 | `0xB5` | Skip 11 zeros, read 5 value bits |
| `1111111111010100` | 16 | `0xB6` | Skip 11 zeros, read 6 value bits |
| `1111111111010101` | 16 | `0xB7` | Skip 11 zeros, read 7 value bits |
| `1111111111010110` | 16 | `0xB8` | Skip 11 zeros, read 8 value bits |
| `1111111111010111` | 16 | `0xB9` | Skip 11 zeros, read 9 value bits |
| `1111111111011000` | 16 | `0xBA` | Skip 11 zeros, read 10 value bits |
| `1111111111011001` | 16 | `0xC2` | Skip 12 zeros, read 2 value bits |
| `1111111111011010` | 16 | `0xC3` | Skip 12 zeros, read 3 value bits |
| `1111111111011011` | 16 | `0xC4` | Skip 12 zeros, read 4 value bits |
| `1111111111011100` | 16 | `0xC5` | Skip 12 zeros, read 5 value bits |
| `1111111111011101` | 16 | `0xC6` | Skip 12 zeros, read 6 value bits |
| `1111111111011110` | 16 | `0xC7` | Skip 12 zeros, read 7 value bits |
| `1111111111011111` | 16 | `0xC8` | Skip 12 zeros, read 8 value bits |
| `1111111111100000` | 16 | `0xC9` | Skip 12 zeros, read 9 value bits |
| `1111111111100001` | 16 | `0xCA` | Skip 12 zeros, read 10 value bits |
| `1111111111100010` | 16 | `0xD2` | Skip 13 zeros, read 2 value bits |
| `1111111111100011` | 16 | `0xD3` | Skip 13 zeros, read 3 value bits |
| `1111111111100100` | 16 | `0xD4` | Skip 13 zeros, read 4 value bits |
| `1111111111100101` | 16 | `0xD5` | Skip 13 zeros, read 5 value bits |
| `1111111111100110` | 16 | `0xD6` | Skip 13 zeros, read 6 value bits |
| `1111111111100111` | 16 | `0xD7` | Skip 13 zeros, read 7 value bits |
| `1111111111101000` | 16 | `0xD8` | Skip 13 zeros, read 8 value bits |
| `1111111111101001` | 16 | `0xD9` | Skip 13 zeros, read 9 value bits |
| `1111111111101010` | 16 | `0xDA` | Skip 13 zeros, read 10 value bits |
| `1111111111101011` | 16 | `0xE1` | Skip 14 zeros, read 1 value bits |
| `1111111111101100` | 16 | `0xE2` | Skip 14 zeros, read 2 value bits |
| `1111111111101101` | 16 | `0xE3` | Skip 14 zeros, read 3 value bits |
| `1111111111101110` | 16 | `0xE4` | Skip 14 zeros, read 4 value bits |
| `1111111111101111` | 16 | `0xE5` | Skip 14 zeros, read 5 value bits |
| `1111111111110000` | 16 | `0xE6` | Skip 14 zeros, read 6 value bits |
| `1111111111110001` | 16 | `0xE7` | Skip 14 zeros, read 7 value bits |
| `1111111111110010` | 16 | `0xE8` | Skip 14 zeros, read 8 value bits |
| `1111111111110011` | 16 | `0xE9` | Skip 14 zeros, read 9 value bits |
| `1111111111110100` | 16 | `0xEA` | Skip 14 zeros, read 10 value bits |
| `1111111111110101` | 16 | `0xF1` | Skip 15 zeros, read 1 value bits |
| `1111111111110110` | 16 | `0xF2` | Skip 15 zeros, read 2 value bits |
| `1111111111110111` | 16 | `0xF3` | Skip 15 zeros, read 3 value bits |
| `1111111111111000` | 16 | `0xF4` | Skip 15 zeros, read 4 value bits |
| `1111111111111001` | 16 | `0xF5` | Skip 15 zeros, read 5 value bits |
| `1111111111111010` | 16 | `0xF6` | Skip 15 zeros, read 6 value bits |
| `1111111111111011` | 16 | `0xF7` | Skip 15 zeros, read 7 value bits |
| `1111111111111100` | 16 | `0xF8` | Skip 15 zeros, read 8 value bits |
| `1111111111111101` | 16 | `0xF9` | Skip 15 zeros, read 9 value bits |
| `1111111111111110` | 16 | `0xFA` | Skip 15 zeros, read 10 value bits |

## DC table 1: 12 codes

Counts for lengths 1..16: 0, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0

| Code | Length | Symbol | Meaning |
|---|---:|---|---|
| `00` | 2 | `0x00` | Read 0 DC difference bits |
| `01` | 2 | `0x01` | Read 1 DC difference bits |
| `10` | 2 | `0x02` | Read 2 DC difference bits |
| `110` | 3 | `0x03` | Read 3 DC difference bits |
| `1110` | 4 | `0x04` | Read 4 DC difference bits |
| `11110` | 5 | `0x05` | Read 5 DC difference bits |
| `111110` | 6 | `0x06` | Read 6 DC difference bits |
| `1111110` | 7 | `0x07` | Read 7 DC difference bits |
| `11111110` | 8 | `0x08` | Read 8 DC difference bits |
| `111111110` | 9 | `0x09` | Read 9 DC difference bits |
| `1111111110` | 10 | `0x0A` | Read 10 DC difference bits |
| `11111111110` | 11 | `0x0B` | Read 11 DC difference bits |

## AC table 1: 162 codes

Counts for lengths 1..16: 0, 2, 1, 2, 4, 4, 3, 4, 7, 5, 4, 4, 0, 1, 2, 119

| Code | Length | Symbol | Meaning |
|---|---:|---|---|
| `00` | 2 | `0x00` | End of block |
| `01` | 2 | `0x01` | Skip 0 zeros, read 1 value bits |
| `100` | 3 | `0x02` | Skip 0 zeros, read 2 value bits |
| `1010` | 4 | `0x03` | Skip 0 zeros, read 3 value bits |
| `1011` | 4 | `0x11` | Skip 1 zeros, read 1 value bits |
| `11000` | 5 | `0x04` | Skip 0 zeros, read 4 value bits |
| `11001` | 5 | `0x05` | Skip 0 zeros, read 5 value bits |
| `11010` | 5 | `0x21` | Skip 2 zeros, read 1 value bits |
| `11011` | 5 | `0x31` | Skip 3 zeros, read 1 value bits |
| `111000` | 6 | `0x06` | Skip 0 zeros, read 6 value bits |
| `111001` | 6 | `0x12` | Skip 1 zeros, read 2 value bits |
| `111010` | 6 | `0x41` | Skip 4 zeros, read 1 value bits |
| `111011` | 6 | `0x51` | Skip 5 zeros, read 1 value bits |
| `1111000` | 7 | `0x07` | Skip 0 zeros, read 7 value bits |
| `1111001` | 7 | `0x61` | Skip 6 zeros, read 1 value bits |
| `1111010` | 7 | `0x71` | Skip 7 zeros, read 1 value bits |
| `11110110` | 8 | `0x13` | Skip 1 zeros, read 3 value bits |
| `11110111` | 8 | `0x22` | Skip 2 zeros, read 2 value bits |
| `11111000` | 8 | `0x32` | Skip 3 zeros, read 2 value bits |
| `11111001` | 8 | `0x81` | Skip 8 zeros, read 1 value bits |
| `111110100` | 9 | `0x08` | Skip 0 zeros, read 8 value bits |
| `111110101` | 9 | `0x14` | Skip 1 zeros, read 4 value bits |
| `111110110` | 9 | `0x42` | Skip 4 zeros, read 2 value bits |
| `111110111` | 9 | `0x91` | Skip 9 zeros, read 1 value bits |
| `111111000` | 9 | `0xA1` | Skip 10 zeros, read 1 value bits |
| `111111001` | 9 | `0xB1` | Skip 11 zeros, read 1 value bits |
| `111111010` | 9 | `0xC1` | Skip 12 zeros, read 1 value bits |
| `1111110110` | 10 | `0x09` | Skip 0 zeros, read 9 value bits |
| `1111110111` | 10 | `0x23` | Skip 2 zeros, read 3 value bits |
| `1111111000` | 10 | `0x33` | Skip 3 zeros, read 3 value bits |
| `1111111001` | 10 | `0x52` | Skip 5 zeros, read 2 value bits |
| `1111111010` | 10 | `0xF0` | Skip 16 zeros |
| `11111110110` | 11 | `0x15` | Skip 1 zeros, read 5 value bits |
| `11111110111` | 11 | `0x62` | Skip 6 zeros, read 2 value bits |
| `11111111000` | 11 | `0x72` | Skip 7 zeros, read 2 value bits |
| `11111111001` | 11 | `0xD1` | Skip 13 zeros, read 1 value bits |
| `111111110100` | 12 | `0x0A` | Skip 0 zeros, read 10 value bits |
| `111111110101` | 12 | `0x16` | Skip 1 zeros, read 6 value bits |
| `111111110110` | 12 | `0x24` | Skip 2 zeros, read 4 value bits |
| `111111110111` | 12 | `0x34` | Skip 3 zeros, read 4 value bits |
| `11111111100000` | 14 | `0xE1` | Skip 14 zeros, read 1 value bits |
| `111111111000010` | 15 | `0x25` | Skip 2 zeros, read 5 value bits |
| `111111111000011` | 15 | `0xF1` | Skip 15 zeros, read 1 value bits |
| `1111111110001000` | 16 | `0x17` | Skip 1 zeros, read 7 value bits |
| `1111111110001001` | 16 | `0x18` | Skip 1 zeros, read 8 value bits |
| `1111111110001010` | 16 | `0x19` | Skip 1 zeros, read 9 value bits |
| `1111111110001011` | 16 | `0x1A` | Skip 1 zeros, read 10 value bits |
| `1111111110001100` | 16 | `0x26` | Skip 2 zeros, read 6 value bits |
| `1111111110001101` | 16 | `0x27` | Skip 2 zeros, read 7 value bits |
| `1111111110001110` | 16 | `0x28` | Skip 2 zeros, read 8 value bits |
| `1111111110001111` | 16 | `0x29` | Skip 2 zeros, read 9 value bits |
| `1111111110010000` | 16 | `0x2A` | Skip 2 zeros, read 10 value bits |
| `1111111110010001` | 16 | `0x35` | Skip 3 zeros, read 5 value bits |
| `1111111110010010` | 16 | `0x36` | Skip 3 zeros, read 6 value bits |
| `1111111110010011` | 16 | `0x37` | Skip 3 zeros, read 7 value bits |
| `1111111110010100` | 16 | `0x38` | Skip 3 zeros, read 8 value bits |
| `1111111110010101` | 16 | `0x39` | Skip 3 zeros, read 9 value bits |
| `1111111110010110` | 16 | `0x3A` | Skip 3 zeros, read 10 value bits |
| `1111111110010111` | 16 | `0x43` | Skip 4 zeros, read 3 value bits |
| `1111111110011000` | 16 | `0x44` | Skip 4 zeros, read 4 value bits |
| `1111111110011001` | 16 | `0x45` | Skip 4 zeros, read 5 value bits |
| `1111111110011010` | 16 | `0x46` | Skip 4 zeros, read 6 value bits |
| `1111111110011011` | 16 | `0x47` | Skip 4 zeros, read 7 value bits |
| `1111111110011100` | 16 | `0x48` | Skip 4 zeros, read 8 value bits |
| `1111111110011101` | 16 | `0x49` | Skip 4 zeros, read 9 value bits |
| `1111111110011110` | 16 | `0x4A` | Skip 4 zeros, read 10 value bits |
| `1111111110011111` | 16 | `0x53` | Skip 5 zeros, read 3 value bits |
| `1111111110100000` | 16 | `0x54` | Skip 5 zeros, read 4 value bits |
| `1111111110100001` | 16 | `0x55` | Skip 5 zeros, read 5 value bits |
| `1111111110100010` | 16 | `0x56` | Skip 5 zeros, read 6 value bits |
| `1111111110100011` | 16 | `0x57` | Skip 5 zeros, read 7 value bits |
| `1111111110100100` | 16 | `0x58` | Skip 5 zeros, read 8 value bits |
| `1111111110100101` | 16 | `0x59` | Skip 5 zeros, read 9 value bits |
| `1111111110100110` | 16 | `0x5A` | Skip 5 zeros, read 10 value bits |
| `1111111110100111` | 16 | `0x63` | Skip 6 zeros, read 3 value bits |
| `1111111110101000` | 16 | `0x64` | Skip 6 zeros, read 4 value bits |
| `1111111110101001` | 16 | `0x65` | Skip 6 zeros, read 5 value bits |
| `1111111110101010` | 16 | `0x66` | Skip 6 zeros, read 6 value bits |
| `1111111110101011` | 16 | `0x67` | Skip 6 zeros, read 7 value bits |
| `1111111110101100` | 16 | `0x68` | Skip 6 zeros, read 8 value bits |
| `1111111110101101` | 16 | `0x69` | Skip 6 zeros, read 9 value bits |
| `1111111110101110` | 16 | `0x6A` | Skip 6 zeros, read 10 value bits |
| `1111111110101111` | 16 | `0x73` | Skip 7 zeros, read 3 value bits |
| `1111111110110000` | 16 | `0x74` | Skip 7 zeros, read 4 value bits |
| `1111111110110001` | 16 | `0x75` | Skip 7 zeros, read 5 value bits |
| `1111111110110010` | 16 | `0x76` | Skip 7 zeros, read 6 value bits |
| `1111111110110011` | 16 | `0x77` | Skip 7 zeros, read 7 value bits |
| `1111111110110100` | 16 | `0x78` | Skip 7 zeros, read 8 value bits |
| `1111111110110101` | 16 | `0x79` | Skip 7 zeros, read 9 value bits |
| `1111111110110110` | 16 | `0x7A` | Skip 7 zeros, read 10 value bits |
| `1111111110110111` | 16 | `0x82` | Skip 8 zeros, read 2 value bits |
| `1111111110111000` | 16 | `0x83` | Skip 8 zeros, read 3 value bits |
| `1111111110111001` | 16 | `0x84` | Skip 8 zeros, read 4 value bits |
| `1111111110111010` | 16 | `0x85` | Skip 8 zeros, read 5 value bits |
| `1111111110111011` | 16 | `0x86` | Skip 8 zeros, read 6 value bits |
| `1111111110111100` | 16 | `0x87` | Skip 8 zeros, read 7 value bits |
| `1111111110111101` | 16 | `0x88` | Skip 8 zeros, read 8 value bits |
| `1111111110111110` | 16 | `0x89` | Skip 8 zeros, read 9 value bits |
| `1111111110111111` | 16 | `0x8A` | Skip 8 zeros, read 10 value bits |
| `1111111111000000` | 16 | `0x92` | Skip 9 zeros, read 2 value bits |
| `1111111111000001` | 16 | `0x93` | Skip 9 zeros, read 3 value bits |
| `1111111111000010` | 16 | `0x94` | Skip 9 zeros, read 4 value bits |
| `1111111111000011` | 16 | `0x95` | Skip 9 zeros, read 5 value bits |
| `1111111111000100` | 16 | `0x96` | Skip 9 zeros, read 6 value bits |
| `1111111111000101` | 16 | `0x97` | Skip 9 zeros, read 7 value bits |
| `1111111111000110` | 16 | `0x98` | Skip 9 zeros, read 8 value bits |
| `1111111111000111` | 16 | `0x99` | Skip 9 zeros, read 9 value bits |
| `1111111111001000` | 16 | `0x9A` | Skip 9 zeros, read 10 value bits |
| `1111111111001001` | 16 | `0xA2` | Skip 10 zeros, read 2 value bits |
| `1111111111001010` | 16 | `0xA3` | Skip 10 zeros, read 3 value bits |
| `1111111111001011` | 16 | `0xA4` | Skip 10 zeros, read 4 value bits |
| `1111111111001100` | 16 | `0xA5` | Skip 10 zeros, read 5 value bits |
| `1111111111001101` | 16 | `0xA6` | Skip 10 zeros, read 6 value bits |
| `1111111111001110` | 16 | `0xA7` | Skip 10 zeros, read 7 value bits |
| `1111111111001111` | 16 | `0xA8` | Skip 10 zeros, read 8 value bits |
| `1111111111010000` | 16 | `0xA9` | Skip 10 zeros, read 9 value bits |
| `1111111111010001` | 16 | `0xAA` | Skip 10 zeros, read 10 value bits |
| `1111111111010010` | 16 | `0xB2` | Skip 11 zeros, read 2 value bits |
| `1111111111010011` | 16 | `0xB3` | Skip 11 zeros, read 3 value bits |
| `1111111111010100` | 16 | `0xB4` | Skip 11 zeros, read 4 value bits |
| `1111111111010101` | 16 | `0xB5` | Skip 11 zeros, read 5 value bits |
| `1111111111010110` | 16 | `0xB6` | Skip 11 zeros, read 6 value bits |
| `1111111111010111` | 16 | `0xB7` | Skip 11 zeros, read 7 value bits |
| `1111111111011000` | 16 | `0xB8` | Skip 11 zeros, read 8 value bits |
| `1111111111011001` | 16 | `0xB9` | Skip 11 zeros, read 9 value bits |
| `1111111111011010` | 16 | `0xBA` | Skip 11 zeros, read 10 value bits |
| `1111111111011011` | 16 | `0xC2` | Skip 12 zeros, read 2 value bits |
| `1111111111011100` | 16 | `0xC3` | Skip 12 zeros, read 3 value bits |
| `1111111111011101` | 16 | `0xC4` | Skip 12 zeros, read 4 value bits |
| `1111111111011110` | 16 | `0xC5` | Skip 12 zeros, read 5 value bits |
| `1111111111011111` | 16 | `0xC6` | Skip 12 zeros, read 6 value bits |
| `1111111111100000` | 16 | `0xC7` | Skip 12 zeros, read 7 value bits |
| `1111111111100001` | 16 | `0xC8` | Skip 12 zeros, read 8 value bits |
| `1111111111100010` | 16 | `0xC9` | Skip 12 zeros, read 9 value bits |
| `1111111111100011` | 16 | `0xCA` | Skip 12 zeros, read 10 value bits |
| `1111111111100100` | 16 | `0xD2` | Skip 13 zeros, read 2 value bits |
| `1111111111100101` | 16 | `0xD3` | Skip 13 zeros, read 3 value bits |
| `1111111111100110` | 16 | `0xD4` | Skip 13 zeros, read 4 value bits |
| `1111111111100111` | 16 | `0xD5` | Skip 13 zeros, read 5 value bits |
| `1111111111101000` | 16 | `0xD6` | Skip 13 zeros, read 6 value bits |
| `1111111111101001` | 16 | `0xD7` | Skip 13 zeros, read 7 value bits |
| `1111111111101010` | 16 | `0xD8` | Skip 13 zeros, read 8 value bits |
| `1111111111101011` | 16 | `0xD9` | Skip 13 zeros, read 9 value bits |
| `1111111111101100` | 16 | `0xDA` | Skip 13 zeros, read 10 value bits |
| `1111111111101101` | 16 | `0xE2` | Skip 14 zeros, read 2 value bits |
| `1111111111101110` | 16 | `0xE3` | Skip 14 zeros, read 3 value bits |
| `1111111111101111` | 16 | `0xE4` | Skip 14 zeros, read 4 value bits |
| `1111111111110000` | 16 | `0xE5` | Skip 14 zeros, read 5 value bits |
| `1111111111110001` | 16 | `0xE6` | Skip 14 zeros, read 6 value bits |
| `1111111111110010` | 16 | `0xE7` | Skip 14 zeros, read 7 value bits |
| `1111111111110011` | 16 | `0xE8` | Skip 14 zeros, read 8 value bits |
| `1111111111110100` | 16 | `0xE9` | Skip 14 zeros, read 9 value bits |
| `1111111111110101` | 16 | `0xEA` | Skip 14 zeros, read 10 value bits |
| `1111111111110110` | 16 | `0xF2` | Skip 15 zeros, read 2 value bits |
| `1111111111110111` | 16 | `0xF3` | Skip 15 zeros, read 3 value bits |
| `1111111111111000` | 16 | `0xF4` | Skip 15 zeros, read 4 value bits |
| `1111111111111001` | 16 | `0xF5` | Skip 15 zeros, read 5 value bits |
| `1111111111111010` | 16 | `0xF6` | Skip 15 zeros, read 6 value bits |
| `1111111111111011` | 16 | `0xF7` | Skip 15 zeros, read 7 value bits |
| `1111111111111100` | 16 | `0xF8` | Skip 15 zeros, read 8 value bits |
| `1111111111111101` | 16 | `0xF9` | Skip 15 zeros, read 9 value bits |
| `1111111111111110` | 16 | `0xFA` | Skip 15 zeros, read 10 value bits |
