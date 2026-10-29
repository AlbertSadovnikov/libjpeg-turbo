# AVX2 32-byte scan-window comparison

Median of per-run mean CPU times; one embedded frame, CPU pinned, five bracketed rounds; no low-level profiling.

| Variant | BGR ms | BGR reduction | Entropy/store ms | Entropy reduction |
|---|---:|---:|---:|---:|
| baseline | 5.9579 | 0.00% | 3.1187 | 0.00% |
| scalar | 5.8943 | 1.07% | 3.0797 | 1.25% |
| avx2-codegen | 5.9770 | -0.32% | 3.1321 | -0.43% |
| avx2-32-local | 6.0773 | -2.00% | 3.2497 | -4.20% |
| avx2-32-persistent | 6.1206 | -2.73% | 3.2749 | -5.01% |
