#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
keys=['fast_mcu_calls','single_hits','pair_hits','fused_fallbacks','bulk_refills','clean_refills','ff_guard_refills','fast_marker_retries','slow_mcu_calls','stuffed_ff_observations','marker_observations']
rows=[]
for camera in json.loads((here/'inventory.json').read_text()):
 g=camera['groups']['1920x1080'];mode=max(g['modes'],key=lambda m:float(m['requested']['fps']));files=sorted(Path(mode['directory']).glob('frame_*.jpg'))
 r=execute(WORK/'bin/clang-diagnostic-probe','count',*files);counts=dict(zip(keys,r['entropy_counters']));total=counts['single_hits']+counts['pair_hits']+counts['fused_fallbacks']
 rows.append({'camera':camera['camera'],'files':[str(p) for p in files],'mean_jpeg_bytes':sum(p.stat().st_size for p in files)/len(files),'counters':counts,'fused_iteration_fallback_percent':100*counts['fused_fallbacks']/total if total else None,'ff_guard_refill_percent':100*counts['ff_guard_refills']/counts['bulk_refills'] if counts['bulk_refills'] else None,'mcus':r['mcus'],'nonzero_coefficients':r['nonzero'],'scope':'Untimed diagnostic original entropy implementation; no reconstruction. Not a valid NV12 benchmark or compiler-training profile.'})
 save(here/'diagnostics.json',rows);print(camera['camera'],counts,'fallback %',rows[-1]['fused_iteration_fallback_percent'],flush=True)
