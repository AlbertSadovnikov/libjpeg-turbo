# Huffman instruction selection and compiler preconditions

GCC 13.3, x86-64, `-O3 -DNDEBUG`, with and without `-mbmi2`.
Run `python3 test/webcam/bmi-current/preconditions/audit.py` to reproduce.
The script currently uses the existing threshold-pair10 source/build directories
under `/tmp/mjpeg-stb-{src,build}`. This is a compiler audit, not a timing test.
Full instruction evidence and semantic-check results are in `summary.json`.

## Where instructions appear

The measured BMI2 fast MCU path has 13 SHRX and 6 SHLX static sites:

| Source operation | Selection |
|---|---|
| DC/AC Huffman lookup, fallback and discard bit peeks | SHRX |
| DC/AC amplitude extraction (`GET_BITS`) | SHRX plus SHLX to construct masks |
| DC/AC JPEG amplitude sign extension (`HUFF_EXTEND`) | SHLX for variable powers of two |
| Fused 10-bit AC lookup | SHRX, then constant mask |

There is no BZHI in that fast path. The earlier audit found one in the
out-of-line slow Huffman helper. See the adjacent `instruction-audit/README.md`
for exact object offsets and source mappings. Bulk refill uses ordinary scalar
loads and constant shifts; BMI2 variable shifts do not accelerate its load itself.

## Explicit control

`probes.c` demonstrates `_bzhi_u32` in a BMI2-targeted function, and inline
assembly wrappers for SHRX/SHLX. The latter guarantee those opcodes on GCC/x86-64;
the installed GCC BMI2 headers do not expose equivalent SHRX/SHLX intrinsics.
They preserve flags and require no memory or condition-code clobbers.
Use a CPU-selected kernel so feature checks occur outside the symbol loop.
An intrinsic expresses the operation, but checking disassembly remains useful
when the exact instruction is a requirement.

The helpers were checked in generic and BMI2 builds, in both AT&T and Intel
assembly dialects: each checked 131,070 amplitude cases (widths 1 through 16)
and all 4,096 pairs of valid 64-bit shift counts. These are helper semantic
checks, not validation of a changed full decoder.

## What prevents selection?

Scalar register SHRX/SHLX/BZHI do not require aligned or nonaliasing memory.
Missing alignment cannot explain why a register mask did not become BZHI.

Reduced probes give concrete examples of the compiler's decisions:

* Signed and unsigned isolated bit extraction both become SHRX + BZHI with
  BMI2 enabled. Adding explicit valid-width bounds does not improve this.
* Combining extraction with JPEG sign extension changes the decision. The
  unsigned expression uses SHLX/AND and reuses mask-related work rather than
  emitting BZHI. Keeping the mask as a separate output also prevents BZHI in
  this example. Whole-expression optimization matters, not just the local idiom.
* `restrict` removes a demonstrable reload in the small alias probe. A `const`
  table pointer alone does not prevent a coefficient store from aliasing it.
* The aligned and unaligned 8-byte `memcpy` probes both compile to one MOV.
  The existing refill already has a suitable scalar load.

The real decoder was also compiled with isolated changes:

| Change | Fast SHRX sites | Fast SHLX sites | `decode_mcu` instruction sites |
|---|---:|---:|---:|
| Control | 13 | 6 | 1669 |
| Explicit DC/fused-entry range facts | 13 | 6 | 1669 |
| Local input/output/LUT `restrict` | 13 | 6 | 1669 |
| Fused-entry alignment 8 | 13 | 6 | 1669 |
| Unsigned GET_BITS mask expression | 13 | 4 | 1630 |

The last column includes the slow and fast code within `decode_mcu`, and
counts disassembled instruction sites, including padding. It is not executed
instruction count or a speed measurement. The annotation experiments did not
unlock additional BMI instructions; this does not prove arbitrary alias or
range changes can never improve the loop. In particular, a local `restrict`
annotation is weaker evidence than a carefully designed private kernel interface.

Range facts must come from validated JPEG tables/the fused-table builder.
Do not assert valid-input limits on malformed JPEG input without establishing
the checks that enforce them. Likewise, nonoverlap between input, LUTs and
coefficient output must be established before applying a noalias contract.
These assumption variants were compiled for inspection, not promoted as decoders.

## Concrete memory-layout opportunity

Our fused entry is 8 bytes but has alignment 2. The lookup member starts at
offset 278, and both allocated tables in the embedded webcam frame start at
addresses congruent to 6 modulo 8. Consequently, 128 of 1024 entry records
straddle a 64-byte cache-line boundary.

Giving the entry type alignment 8 keeps its size at 8, moves the lookup member
to offset 280, and produces aligned table addresses. No entry record then
straddles a cache line. This does not require 64-byte table alignment.

This is a measured layout fact, not a demonstrated speedup: individual field
loads may stay within one line even when the complete record crosses it, and
the actual lookup distribution determines traffic. Benchmark this as a separate
change. Do not merely assert 64-byte alignment on the current allocator.

No production codec source was changed by this audit.
