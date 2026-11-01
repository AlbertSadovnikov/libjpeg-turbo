#!/usr/bin/env python3
"""Inspect only the Clang binaries used for JPEG-to-NV12 measurement."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

here = Path(__file__).resolve().parent
out = here / 'analysis'; out.mkdir(exist_ok=True)
work = Path('/tmp/mjpeg-pgo-lto')
summary = {}
for tier in ('base', 'pgo', 'lto', 'pgo-lto'):
    binary = work / ('clang-' + tier + '-sequence')
    symbols = []
    for line in subprocess.check_output(['nm', '-S', str(binary)], text=True).splitlines():
        match = re.match(r'([0-9a-f]+) ([0-9a-f]+) ([tT]) (.*)', line)
        if match:
            symbols.append(dict(address=int(match[1], 16), size=int(match[2], 16), name=match[4]))
    record = {'functions': {}}
    sections = subprocess.check_output(['size', '-A', str(binary)], text=True)
    record['text_section_bytes'] = int(re.search(r'(?m)^\.text\s+(\d+)', sections)[1])
    for name in ('decode_mcu', 'jpeg_read_raw_data', 'jpeg_start_decompress'):
        candidates = [s for s in symbols if s['name'] == name or s['name'].startswith(name + '.llvm.')]
        # The other decode_mcu symbol is the smaller lossless decoder.
        symbol = max(candidates, key=lambda s: s['size'])
        assembly = subprocess.check_output(['objdump', '-d', '--no-show-raw-insn', '-Mintel',
            '--start-address=' + str(symbol['address']),
            '--stop-address=' + str(symbol['address'] + symbol['size']), str(binary)], text=True)
        (out / (tier + '-' + name + '.asm')).write_text(assembly)
        calls = []; ops = {}
        for line in assembly.splitlines():
            match = re.match(r'^\s*[0-9a-f]+:\s+([a-z][a-z0-9]*)\s*(.*)', line)
            if not match: continue
            op, operands = match.groups()
            if op in ('shrx', 'shlx', 'bzhi', 'sarx', 'bextr', 'pext', 'pdep'):
                ops[op] = ops.get(op, 0) + 1
            if op == 'call': calls.append(operands)
        record['functions'][name] = dict(symbol, bmi_static_sites=ops, calls=calls)
    record['idct_object_hashes'] = {obj: hashlib.sha256(subprocess.check_output(
        ['ar', 'p', str(work / ('clang-' + tier) / 'libjpeg.a'), obj])).hexdigest()
        for obj in ('jidctfst-sse2.asm.o', 'jidctint-avx2.asm.o')}
    summary[tier] = record
profile = work / 'clang-pgo-lto-profile/merged.profdata'
for function in ('jpeg_read_raw_data', 'decompress_onepass'):
    text = subprocess.check_output(['llvm-profdata-18', 'show', '--function=' + function,
                                    '--counts', '--ic-targets', str(profile)], text=True)
    (out / (function + '-profile.txt')).write_text(text)
(out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({tier: dict(text_bytes=r['text_section_bytes'],
    function_bytes={name: f['size'] for name, f in r['functions'].items()},
    huffman_bmi=r['functions']['decode_mcu']['bmi_static_sites']) for tier, r in summary.items()}, indent=2))
