#!/usr/bin/env python3
"""Only JPEG-to-NV12 timing and output hashes, no PGO or LTO."""
from pathlib import Path
import json
import statistics
import subprocess
import argparse

here = Path(__file__).resolve().parent
config = json.loads((here/'experiment.json').read_text())
split = json.loads((here.parent/'pgo-lto/build-summary.json').read_text())['split']
frames = split['heldout']; assert len(frames) == 90
parser=argparse.ArgumentParser()
parser.add_argument('--variants',nargs='+',choices=['huffman','idct','both','cold'])
args=parser.parse_args()
variants=args.variants or ['huffman','idct','both']
prefix='-'.join(variants)+'-' if args.variants else ''
names = [c+'-'+v for c in ('gcc','clang') for v in ('base',*variants)]
records = []; hashes = {}
for mode in ('accurate','fast'):
    for trial in range(3):
        order = names[trial:]+names[:trial]
        if trial % 2: order.reverse()
        for name in order:
            result = subprocess.run(['taskset','-c','0',config[name]['sequence_binary'],mode,'3',*frames],
                                    check=True,capture_output=True,text=True)
            assert not result.stderr,result.stderr
            row=json.loads(result.stdout)
            if mode in hashes: assert row['hash']==hashes[mode],(name,mode)
            else:hashes[mode]=row['hash']
            row.update(variant=name,mode=mode,trial=trial);records.append(row)
            (here/(prefix+'results.json')).write_text(json.dumps(records,indent=2)+'\n')
        print(mode,trial,'complete',flush=True)
summary={}
for name in names:
    summary[name]={mode+'_ms':statistics.mean(r['mean_ms'] for r in records if r['variant']==name and r['mode']==mode)
                   for mode in ('accurate','fast')}
(here/(prefix+'summary.json')).write_text(json.dumps(dict(cases=summary,hashes=hashes,
    method='No PGO/LTO; three rotated/reversed rounds; 90 held-out preloaded frames, three measured passes after full warmup; CPU 0; matching NV12 hashes'),indent=2)+'\n')
print(json.dumps(summary,indent=2))
