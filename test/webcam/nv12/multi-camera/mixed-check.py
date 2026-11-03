#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
B=WORK/'bin';inventory=json.loads((here/'inventory.json').read_text());assert len(inventory)==2;out={}
for size in ('640x480','1280x720','1920x1080'):
 streams=[]
 for c in inventory:
  mode=max(c['groups'][size]['modes'],key=lambda m:float(m['requested']['fps']));streams.append(sorted(Path(mode['directory']).glob('frame_*.jpg')))
 files=[p for pair in zip(*streams) for p in pair];out[size]={}
 for cc in ('clang','gcc'):
  stock=execute(B/(cc+'-camera-stock'),'validate',1,*files);exact=execute(B/(cc+'-camera-exact'),'validate',*files)
  fast=next(r for r in exact['cases'] if r['idct']=='fast' and r['mode']==3);assert fast['output_hash']==stock['hash']
  out[size][cc]={'stock':stock,'exact':exact}
  if cc=='gcc':assert execute(B/'gcc-camera-deferred','validate',*files)==exact
 save(here/'mixed-validation.json',out);print(size,'alternating cameras/table changes passed.',flush=True)
