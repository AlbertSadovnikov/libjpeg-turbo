# Historical mixed-profile comparison — superseded

This cohort compares stock GCC without PGO/LTO against a candidate containing
PGO-trained objects. The user subsequently required **no PGO in comparisons**,
with LTO allowed. These results are retained as historical evidence and are
excluded from current headline comparisons. See `../lto-only/` for the clean,
matched-compiler, LTO-without-PGO rebuild and comparison. Do not reuse retained
profiled codec archives for new comparisons.
