# Current-entry consumed-bit/span control word — rejected

No PGO, no explicit CPU tuning, matched LTO, same current reduced-UV contract.
`control-word.patch` keeps the LUT entry eight bytes, combining consumed-bit
count and span into one UINT16 (low/high byte). Step1/step2 remain byte fields.
The hypothesis is one guard-control load instead of two independent byte loads;
coefficient payload remains late. This does not prefetch the next entry.

Literal serialization of every quantized coefficient and quantizer table
matches control on all 120 capture frames, six fixtures and four quantizer
mutation/selection inputs, separately under Clang and GCC. Full NV12, mixed
table changes, both IDCT modes and padding also match. Coefficient byte streams
are compared in memory and discarded; compact per-input hashes remain in
`coefficients.json`. This is not just a final-MCU or output hash check.

| Five current/control-word/current brackets | Control | Candidate | Latency change |
|---|---:|---:|---:|
| Clang | See shared raw records | See shared raw records | +3.21% |
| GCC | See shared raw records | See shared raw records | +2.64% |

All five brackets regress for each compiler. Same-binary noise controls are
retained in `../next-round/cd-results.json`. Fewer source loads do not guarantee
a shorter critical path: extraction/masking and register allocation change.
No exact cycle cause is claimed. This branch is stopped; no rare-refill
outlining or additional speculative metadata variants were stacked onto it.

```
python3 test/webcam/nv12/entropy-control-word/build.py
python3 test/webcam/nv12/next-round/run-cd.py
python3 test/webcam/nv12/next-round/audit.py
```

Requires the prepared `next-round/` baseline. Only `jdhuff.c.o` changes in each
codec archive; all other members are checked identical. Codec flags match
untuned/no-PGO Clang ThinLTO and GCC LTO. CPU 0, 90 preloaded frames, three
measured passes after warmup; source is the same one captured scene.
Production source trees are unchanged. No commit or push.
