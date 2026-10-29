#!/usr/bin/env python3
"""Decode-only perf counters, alternating paired trials, no multiplexing."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parent
out = root / 'hardware-results'
out.mkdir(exist_ok=True)
groups = {
    'execution': 'cycles:u,instructions:u,branches:u,branch-misses:u',
    'cache': 'L1-dcache-loads:u,L1-dcache-load-misses:u,cache-references:u,cache-misses:u',
}
results = []
with tempfile.TemporaryDirectory(prefix='mjpeg-perf-') as tmp:
    ctl = Path(tmp) / 'control'
    os.mkfifo(ctl)
    os.mkfifo(str(ctl) + '.ack')
    for mode in ('entropy', 'full'):
        for group, events in groups.items():
            for trial in range(5):
                for variant in (('baseline', 'scalar') if trial % 2 == 0 else ('scalar', 'baseline')):
                    name = f'{mode}-{group}-{trial}-{variant}'
                    raw = out / (name + '.csv')
                    cmd = ['perf', 'stat', '-D', '-1', '--control', f'fifo:{ctl},{ctl}.ack',
                           '-x', ';', '-o', str(raw), '-e', '{' + events + '}', '--',
                           'taskset', '-c', '0', str(root / ('driver-' + variant)), mode, '100', '5', '0']
                    run = subprocess.run(cmd, env=dict(os.environ, MJPEG_PERF_CONTROL=str(ctl)),
                                         capture_output=True, text=True, timeout=60)
                    if run.returncode:
                        raise RuntimeError(run.stdout + run.stderr + raw.read_text())
                    counters = {}
                    for line in raw.read_text().splitlines():
                        fields = line.split(';')
                        if len(fields) < 5 or fields[2] == '':
                            continue
                        if not fields[0].strip().isdigit() or float(fields[4]) < 99.9:
                            raise RuntimeError('Unsupported or multiplexed counter: ' + line)
                        counters[fields[2]] = int(fields[0])
                    row = json.loads(run.stdout)
                    row.update(variant=variant, group=group, trial=trial, counters=counters)
                    results.append(row)
                    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
                    print(name, flush=True)
