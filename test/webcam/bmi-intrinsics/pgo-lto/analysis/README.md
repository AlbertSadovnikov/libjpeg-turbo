# What Clang PGO and ThinLTO changed in JPEG-to-NV12

Inspection of the exact Clang binaries from the NV12 matrix. Run
`python3 test/webcam/bmi-intrinsics/pgo-lto/inspect.py` for symbol sizes,
disassembly, SIMD object hashes and profile-target reports (`summary.json`).

## Observed changes

1. **PGO peels three iterations of the AC long-Huffman-code search.**
   The source-located loop-unroll remark identifies jdhuff.c:835, the
   HUFF_DECODE_FAST call in the AC fallback. Its variable-length search is
   `while (prefix >= htbl->maxcode16[nb]) nb++;`. Peeling puts the first
   three iterations before the residual loop, retaining the general fallback.
   This is not unrolling the whole AC coefficient loop or decoding three
   independent symbols in parallel. The compiler-reported hotness is 2,395,071.

2. **PGO peels the first IDCT block iteration.**
   The remark identifies jdcoefct.c:160, the `xindex < useful_width` loop in
   decompress_onepass. This webcam's 4:2:2 MCU has two horizontal Y blocks
   and one block for each chroma component, making one- and two-iteration
   loops common. The first iteration is extracted; the remainder stays general.
   The compiler-reported hotness is 7,775,030. The IDCT callback is still indirect.

3. **PGO lays out the normal raw-output path separately from cold checks.**
   In jpeg_read_raw_data, validation and progress-callback paths move after
   the successful return. Entry pushes drop from five to three; extra saves
   occur only on cold paths. Checks are retained. The function actually grows
   from 296 to 387 bytes, illustrating why smaller total functions are not
   necessarily faster on their common path.

4. **ThinLTO inlines output_pass_setup into jpeg_start_decompress when PGO
   is enabled.** Its actual linker remark records this successful cross-TU
   inline. The start function grows from 213 baseline bytes to 648 bytes.
   It is setup work, not a new SIMD IDCT implementation. Other ThinLTO effects
   include internalization/layout/dead-code elimination; we have not assigned
   a timing contribution to each effect.

## Exact code-generation evidence

| Clang build | Executable .text bytes | Huffman decode_mcu bytes |
|---|---:|---:|
| Baseline | 1,249,648 | 5,494 |
| PGO | 1,118,559 | 6,214 |
| ThinLTO | 775,264 | 5,503 |
| PGO + ThinLTO | 741,024 | 6,309 |

The .text totals include the benchmark and otherwise unused codec functions;
the roughly 41% reduction is not a 41% reduction in executed decoder code.
The hot Huffman function grows roughly 15%. Cold-code removal alone does not
prove an instruction-cache explanation for the measured speedup.

All four Huffman functions retain the same static counts: **17 SHRX, 8 SHLX,
4 BZHI** across the combined fast/slow function. No new PEXT/PDEP implementation
appears. The archive objects `jidctint-avx2.asm.o` and `jidctfst-sse2.asm.o`
are byte-identical across all four Clang builds.

For source-located compile remarks, jdhuff.c and the 8-bit jdapistd/jdcoefct
wrappers were recompiled with the exact build flags plus `-gline-tables-only`
and optimization-record flags. Each inspected native .text matches its
measured object byte-for-byte. ThinLTO link remarks were obtained by relinking
the same bitcode archives with LLVMgold's `opt-remarks-filename` option;
those relinked .text sections also match the measured binaries byte-for-byte.
Large raw per-module remarks and disassemblies are retained locally.

Some remarks are **missed** opportunities, not applied transformations: the
Huffman CHR remarks, for example, report `SelectNotBiased`. They are not
evidence that control-height reduction produced the speedup.

## Important remaining opportunity: indirect-call profiling

The existing front-end instrumentation profiles report **zero indirect-call
sites** for jpeg_read_raw_data and decompress_onepass. The corresponding
entropy/IDCT callback machinery remains indirect in the binary. Thus the
observed gain cannot be described as full pipeline devirtualization.

A local Clang 18 probe confirms that IR-based `-fprofile-generate` inserts
`__llvm_profile_instrument_target` for an indirect call; our existing
`-fprofile-instr-generate` probe does not. The next useful experiment is IR
PGO with ThinLTO, training on the same actual JPEG-to-NV12 path, then checking
whether call-target promotion/inlining happens and improves held-out timing.
That experiment has not yet been run.

The existing timing matrix suggests most of the gain comes with PGO itself:
accurate NV12 improves about 3.0%, then ThinLTO adds about 0.7% relative to
PGO; fast improves about 1.9%, then ThinLTO adds about 1.3%. These are aggregate
measurements. Isolating individual compiler passes would require further A/B
runs; assembly inspection does not attribute an exact percentage to a pass.
