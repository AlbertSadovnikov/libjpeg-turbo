#!/usr/bin/env python3
"""Print canonical Huffman codes from a JPEG's DHT segments (not lookup tables)."""
from pathlib import Path
import sys


def dump(path):
    data = path.read_bytes()
    if data[:2] != b'\xff\xd8':
        raise ValueError('Not a JPEG')
    print(f'# Huffman codes: {path.name}\n')
    pos = 2
    while pos < len(data):
        if data[pos] != 0xff:
            raise ValueError('Expected JPEG marker')
        while data[pos] == 0xff:
            pos += 1
        marker = data[pos]
        pos += 1
        if marker in (0xda, 0xd9):  # Baseline sample: tables precede first scan.
            break
        if marker == 0x01 or 0xd0 <= marker <= 0xd8:
            continue
        length = int.from_bytes(data[pos:pos + 2], 'big')
        if length < 2 or pos + length > len(data):
            raise ValueError('Invalid segment length')
        payload = data[pos + 2:pos + length]
        pos += length
        if marker != 0xc4:
            continue
        offset = 0
        while offset < len(payload):
            info = payload[offset]
            counts = payload[offset + 1:offset + 17]
            if len(counts) != 16:
                raise ValueError('Truncated DHT')
            offset += 17
            symbols = payload[offset:offset + sum(counts)]
            if len(symbols) != sum(counts):
                raise ValueError('Truncated symbols')
            offset += len(symbols)
            ac = info >> 4
            if ac not in (0, 1):
                raise ValueError('Invalid table class')
            print(f'## {"AC" if ac else "DC"} table {info & 15}: {len(symbols)} codes\n')
            print('Counts for lengths 1..16: ' + ', '.join(map(str, counts)) + '\n')
            print('| Code | Length | Symbol | Meaning |')
            print('|---|---:|---|---|')
            code = index = 0
            for size, count in enumerate(counts, 1):
                for _ in range(count):
                    symbol = symbols[index]
                    if not ac:
                        meaning = f'Read {symbol} DC difference bits'
                    elif symbol == 0:
                        meaning = 'End of block'
                    elif symbol == 0xf0:
                        meaning = 'Skip 16 zeros'
                    else:
                        meaning = f'Skip {symbol >> 4} zeros, read {symbol & 15} value bits'
                    print(f'| `{code:0{size}b}` | {size} | `0x{symbol:02X}` | {meaning} |')
                    code += 1
                    index += 1
                code <<= 1
            print()


if __name__ == '__main__':
    default = Path(__file__).resolve().parents[2] / 'benchmarks/data/webcam_1920x1080_422.jpg'
    dump(Path(sys.argv[1]) if len(sys.argv) > 1 else default)
