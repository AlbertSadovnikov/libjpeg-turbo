# Where GCC emitted BMI2

Audited the exact `jdhuff.c.o` measured in `../README.md`: GCC 13.3, `-O3
-DNDEBUG -mbmi2`, threshold-plus-pair decoder. Compile again with `-g` and
require the complete `.text` bytes to match the measured release object before
using DWARF/addr2line. This equality holds for the control, BMI2, and all three
manual candidates. Proof hashes and every instruction's inline source stack
are saved in `summary.json`. Addresses below are offsets in the object, not
runtime ASLR addresses.

## Static instruction sites in the measured BMI2 object

| Path | SHRX | SHLX | BZHI |
|---|---:|---:|---:|
| Fast MCU decoder | 13 | 6 | 0 |
| Slow MCU decoder | 5 | 6 | 0 |
| Slow bit-fill/Huffman helpers | 2 | 1 | 1 |
| Table setup/building | 9 | 10 | 0 |
| Total | 29 | 23 | 1 |

The fast/slow MCU routines are inlined into the same machine-code symbol,
`decode_mcu`; DWARF inline stacks distinguish them. Static counts are not
execution counts: table setup, initial table construction, and fallback sites
have very different frequencies from repeated coefficient decoding.

## Fast-path source mapping

Source paths are under `/tmp/mjpeg-stb-src/threshold-pair10/src/`, reproducible
from the retained threshold-pair10 patch. Counts include duplicated compiler
paths/loop versions, not separate source operations:

| Source operation | Source line in jdhuff.c | Instructions | Object addresses |
|---|---:|---|---|
| DC Huffman lookup and long-code fallback | 799 | 3 SHRX | 1d40, 28e6, 2d41 |
| Receive DC amplitude bits | 802 | SHLX + SHRX | 1da7, 1daf |
| Extend signed DC amplitude | 803 | 2 SHLX | 1db4, 1dc8 |
| Fused two-symbol 10-bit lookup | 823 | 2 SHRX | 1e76, 1f42 |
| Regular AC lookup/long-code fallback | 835 | 3 SHRX | 1ee4, 2147, 22fd |
| Receive fallback AC amplitude bits | 842 | SHLX + SHRX | 2012, 201b |
| Extend signed fallback AC amplitude | 843 | 2 SHLX | 2031, 2043 |
| AC coefficient-discard path | 854 | 3 SHRX | 245c, 24d7, 260d |

The `PEEK_BITS`/`GET_BITS` macros in `jdhuff.h` produce variable right shifts
of the reservoir. With BMI2, GCC already uses three-operand **SHRX** and can
avoid the ordinary x86 variable-shift CL-register constraint. The bulk refill
itself uses constant shifts (48/8 bits), not these dynamic SHLX sites.

Dynamic value masks in `GET_BITS` still use a power-of-two shift, subtract-one,
and AND in the fast path. `HUFF_EXTEND` creates additional shifted thresholds
and signed-adjustment masks. That was a concrete place to test forced BZHI
and simpler C algebra. The compiler-generated BZHI at object offset **156a**
is inside `jpeg_huff_decode`, the slow out-of-line helper, not the fast MCU
coefficient loop.

## Hardware sampling

`perf record -F 1999 -e cycles:u` on 1,000 entropy passes (five warmups) captured
about 5,000 samples with zero lost samples. The debug sampling binary executes
the same Huffman `.text`. Decode hash matches the control.

- 93.87% of all samples: `decode_mcu`.
- 5.23%: the harness's MCU coefficient-buffer `memset`.
- Inside `decode_mcu`, local samples cluster around the pair lookup, natural-
  order index loads, coefficient stores, fallback lookup extraction and loop.
  One fallback-lookup SHRX location carries 6.17% of local samples; sampled
  coefficient-store PCs carry more than individual bit-manipulation sites.

These are approximate **cycle sample locations**, not instruction latencies.
Skid and dependency stalls can place samples at a following instruction; the
store percentages do not prove memory-bandwidth saturation. The report does
not assign exact fractions of decoding time to SHRX itself. No instruction-
execution frequency claim is derived from the static table.

Reproduce source mapping:

```sh
python3 test/webcam/bmi-current/audit.py --manual
```

This requires the retained original/BMI/manual builds under `/tmp`. Annotated
assembly, perf data and detailed sample text are local generated artifacts.
`summary.json` is the compact mapping/proof record. For the actual manual
candidate results, see [the experiment report](../../bmi-intrinsics/README.md).
