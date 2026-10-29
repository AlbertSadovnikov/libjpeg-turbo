#!/usr/bin/env python3
"""Decode one toy baseline-JPEG block, tracing every bit consumed.

Uses invented Huffman tables and an already unstuffed bit string, not a JPEG
file. For readability, matches codes one bit at a time instead of using the
optimized decoder's 8-bit lookup. AC positions are in zigzag order.
"""

# Huffman symbol -> meaning:
# DC: number of value bits. AC: high nibble = zero run, low nibble = value bits.
DC = {"0": 0, "10": 2, "110": 3}
AC = {"0": 0x00, "10": 0x01, "110": 0x12, "1110": 0x03}

#                DC +5    AC +1  skip 1, -2   AC +5    skip 1, +2  EOB
BITSTREAM = "".join("110 101   10 1   110 01   1110 101   110 10   0".split())
position = 0


def read_bits(count):
    global position
    bits = BITSTREAM[position:position + count]
    if len(bits) != count:
        raise ValueError("Unexpected end of bitstream")
    position += count
    return bits


def decode_symbol(table, name):
    start = position
    code = ""
    path = []
    while len(code) < max(map(len, table)):
        code += read_bits(1)
        path.append(code)
        if code in table:
            symbol = table[code]
            print(f"bits [{start:02}:{position:02}] {name}: "
                  f"{' -> '.join(path)} => symbol 0x{symbol:02x}")
            return symbol
    raise ValueError(f"Unknown Huffman code: {code}")


def decode_value(size):
    if size == 0:
        return 0
    start = position
    bits = read_bits(size)
    value = int(bits, 2)
    # JPEG's signed amplitude convention, not two's complement.
    if bits[0] == "0":
        value -= (1 << size) - 1
    print(f"bits [{start:02}:{position:02}] value: {bits} => {value:+d}")
    return value


def main():
    print(f"Bitstream ({len(BITSTREAM)} bits): {BITSTREAM}\n")
    coefficients = [0] * 64
    previous_dc = 100
    size = decode_symbol(DC, "DC")
    difference = decode_value(size)
    coefficients[0] = previous_dc + difference
    print(f"  DC = previous {previous_dc} + difference {difference:+d}"
          f" = {coefficients[0]}\n")

    k = 1
    while k < 64:
        symbol = decode_symbol(AC, "AC")
        run, size = symbol >> 4, symbol & 15
        if size == 0:
            if run == 0:
                print(f"  EOB: positions {k}..63 remain zero\n")
                break
            if run == 15:
                k += 16
                if k > 64:
                    raise ValueError("Zero run exceeds block")
                continue
            raise ValueError("Invalid baseline AC symbol")
        k += run
        if k >= 64:
            raise ValueError("Coefficient exceeds block")
        coefficients[k] = decode_value(size)
        print(f"  Skip {run} zero(s); coefficient[{k}] = {coefficients[k]:+d}\n")
        k += 1

    print("Coefficients in zigzag order:")
    print(coefficients)
    print(f"Consumed {position}/{len(BITSTREAM)} bits.")
    assert coefficients == [105, 1, 0, -2, 5, 0, 2] + [0] * 57
    assert position == len(BITSTREAM)


if __name__ == "__main__":
    main()
