#!/usr/bin/env python3
"""Confirm full BGR decoding on all 120 preloaded webcam frames."""
import csv
import io
import json
from pathlib import Path
import statistics
import subprocess

here=Path(__file__).resolve().parent
root=here.parents[2]
out=here/'sequence'
out.mkdir(exist_ok=True)
builds=dict(baseline=Path('/tmp/mjpeg-google-bench'),
            scalar=Path('/tmp/mjpeg-entropy-opt-build/bulk-once'),
            pair10=Path('/tmp/mjpeg-multi10-branchless'))
sources=dict(baseline=root,scalar=Path('/tmp/mjpeg-entropy-opt-src/bulk-once'),
             pair10=Path('/tmp/mjpeg-multisymbol-branchless-src'))
for name,build in builds.items():
    subprocess.run(['cc','-O3','-Wall','-Wextra','-I'+str(build),'-I'+str(sources[name]/'src'),
                    str(root/'test/webcam/benchmark.c'),str(build/'libjpeg.a'),'-lm',
                    '-o',str(out/name)],check=True)
frames=sorted((root/'test/webcam/20261023T230418Z').glob('frame_*.jpg'))
assert len(frames)==120
records=[]
for trial in range(3):
    order=list(builds)
    order=order[trial:]+order[:trial]
    for name in order:
        result=subprocess.run(['taskset','-c','0',str(out/name),'bgr','3',*map(str,frames)],
                              capture_output=True,text=True,check=True)
        assert not result.stderr
        (out/f'{trial}-{name}.csv').write_text(result.stdout)
        rows=list(csv.DictReader(io.StringIO(result.stdout)))
        assert len(rows)==360
        records.append(dict(trial=trial,variant=name,mean_ms=statistics.mean(float(r['total_ms']) for r in rows)))
summary=dict(frames=120,passes_per_trial=3,trials=3,records=records,
             mean_ms={name:statistics.mean(r['mean_ms'] for r in records if r['variant']==name) for name in builds})
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
