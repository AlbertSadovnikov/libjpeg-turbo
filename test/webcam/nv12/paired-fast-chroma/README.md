# Paired stock-fast-exact chroma

Retained as a separately selectable output contract. The AVX2 kernel pairs Cb
and Cr IFAST transforms using independent quantizers, then averages rows only
after the native byte rounding/clipping. Whole NV12 matches public stock-fast
decoding; this is not a claim of equality to accurate IDCT.

## Confirmation against stock fast

| Compiler | Control | Candidate | Time reduction |
|---|---:|---:|---:|
| clang | 4.5495 ms | 3.1615 ms | 30.51% |
| gcc | 4.5738 ms | 3.3569 ms | 26.61% |

Same Ryzen 9 3900X, CPU 0, 90 preloaded capture frames, three separate
control/candidate/control brackets, six passes per invocation. Every bracket
improved. Both sides use matched O3/LTO, no PGO, no explicit mtune/march/mcpu.
Clang uses ThinLTO; GCC uses ordinary LTO. BMI2 entropy and native support are
matched. Timing excludes loading, allocation, hashing and diagnostics.

The initial five-bracket cohort also improved every bracket: Clang 4.5438 →
3.1628 ms (30.39%), GCC 4.6530 → 3.3929 ms (27.08%). These are one capture
scene; broader workload/CPU evidence remains outstanding. See `summary.json`,
`results.json` and `../next-round/confirm-{results,summary}.json`.

## Correctness and implementation

`build.py` saves generated `fast.asm` and builds the paired kernel and wrappers.
`check.py` compares 16,200 captured pairs, 10,000 synthetic pairs and 10,000
in-place quantizer changes against two native SSE2 IFAST transforms plus byte
averaging/interleave. Separate Cb/Cr multipliers, signed full-range inputs,
unaligned padded output and unchanged padding are covered. The direct reference
uses scalar/reference packing, so its 75.95 → 21.11 ns result is not a pipeline
speedup claim or comparison with optimized stock packing.

`run.py` validates all 120 captures, six dense/sparse/progressive/restart/tail
fixtures, independent chroma quantizer-selector mutations and mixed streams.
Full arrays are compared literally in the driver; public stock-fast output
hashes also match. Accurate IDCT takes its existing fallback. Reduced mode 2
keeps its existing output. No new claim covers 4:2:0, arbitrary edge dimensions
or unsupported CPUs. `validation.json`, `kernel.json` and `fixture-hashes.json`
retain the evidence.

## Use and reproduce

```
python3 test/webcam/nv12/paired-fast-chroma/build.py
python3 test/webcam/nv12/paired-fast-chroma/check.py
python3 test/webcam/nv12/paired-fast-chroma/run.py
taskset -c 0 /tmp/mjpeg-paired-fast-chroma/nv12 fast 3 6 JPEG...
```

The alias selects mode **3** explicitly; this does not replace the preferred
reduced-UV contract. `../next-round/selections.json` records binary hashes.
The saved codec patch and source-only recovery recipe are documented in
`../next-round/README.md`. Production src/simd are unchanged.
