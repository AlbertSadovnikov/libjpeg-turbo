#!/usr/bin/env python3
"""Run prebuilt embedded-frame drivers; keep native and simulated results separate."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent
out = root / 'results'
out.mkdir(exist_ok=True)
native = []
for mode in ('entropy', 'full'):
    for kib in (0, 32, 2048, 32768):
        for trial in range(3):
            for variant in (('baseline', 'scalar') if trial % 2 == 0 else ('scalar', 'baseline')):
                cmd = ['taskset', '-c', '0', str(root / ('driver-' + variant)), mode, '30', '3', str(kib)]
                row = json.loads(subprocess.check_output(cmd, text=True))
                row.update(variant=variant, trial=trial)
                native.append(row)
                (out / 'native.json').write_text(json.dumps(native, indent=2) + '\n')
profiles = []
for mode, kib in (('entropy', 0), ('entropy', 2048), ('full', 0), ('full', 2048)):
    for variant in ('baseline', 'scalar'):
        name = f'{mode}-{kib}-{variant}'
        profile = out / (name + '.callgrind')
        cmd = ['valgrind', '--tool=callgrind', '--cache-sim=yes', '--branch-sim=yes',
               '--I1=32768,8,64', '--D1=32768,8,64', '--LL=524288,8,64',
               '--instr-atstart=no', '--collect-atstart=no',
               '--callgrind-out-file=' + str(profile),
               str(root / ('driver-' + variant)), mode, '3', '2', str(kib)]
        with (out / (name + '.log')).open('w') as log:
            subprocess.run(cmd, stdout=log, stderr=log, check=True)
        lines = profile.read_text().splitlines()
        events = next(x.split()[1:] for x in lines if x.startswith('events:'))
        totals = next(x.split()[1:] for x in lines if x.startswith('totals:'))
        profiles.append(dict(mode=mode, disturbance_kib=kib, variant=variant,
                             frames=3, events=dict(zip(events, map(int, totals)))))
        (out / 'simulated.json').write_text(json.dumps(profiles, indent=2) + '\n')
print('Wrote native.json and simulated.json')
