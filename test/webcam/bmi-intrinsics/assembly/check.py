#!/usr/bin/env python3
"""Check the exact private assembly kernels under GCC/Clang, both dialects."""
from pathlib import Path
import json
import subprocess

here = Path(__file__).resolve().parent
records = {}
for compiler in ('gcc', 'clang'):
    for dialect in ('att', 'intel'):
        source = Path('/tmp/mjpeg-assembly-src') / (compiler + '-pair') / 'src/jdhuff.c'
        base = Path('/tmp/mjpeg-bmi-current-build/bmi2') if compiler == 'gcc' else Path('/tmp/mjpeg-clang-build/clang-control')
        binary = '/tmp/mjpeg-assembly-check-' + compiler + '-' + dialect
        subprocess.run([compiler, '-O3', '-DNDEBUG', '-mbmi2', '-masm=' + dialect,
                        '-I' + str(base), '-I' + str(source.parent),
                        '-DMJPEG_ASM_SOURCE="' + str(source) + '"', str(here / 'check.c'),
                        str(base / 'libjpeg.a'), '-lm', '-o', binary], check=True)
        result = subprocess.run([binary], check=True, capture_output=True, text=True)
        records[compiler + '-' + dialect] = result.stdout.strip()
        print(compiler, dialect, result.stdout.strip(), flush=True)
(here / 'helper-checks.json').write_text(json.dumps(records, indent=2) + '\n')
