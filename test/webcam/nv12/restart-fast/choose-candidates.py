#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
record=json.loads((here/'separate-build-summary.json').read_text())['records'];confirm=json.loads((here/'separate-confirm-summary.json').read_text());assert len(json.loads((here/'separate-coefficients.json').read_text())['files'])==2325
result={}
for cc in ('clang','gcc'):
 r=record[cc+'-rst-separate-fast'];assert sha(r['binary'])==r['sha256']
 life=next(v for v in confirm if v['compiler']==cc and 'Microsoft' in v['camera']);assert all(v['change_percent']<0 for v in life['brackets'])
 alias=Path('/tmp/mjpeg-restart-fast')/(cc+'-nv12')
 if alias.is_symlink():alias.unlink()
 assert not alias.exists();alias.symlink_to(r['binary'])
 result[cc]={'executable':str(alias),'target':r['binary'],'sha256':r['sha256'],'arguments':['fast','3','PASSES','JPEG...'],'output_contract':'Stock-fast-exact NV12 on tested inputs','scope':'Separate experimental candidate for restart-enabled workloads. Existing defaults preserved because non-restart measurements show a small regression.','pgo':False,'explicit_tune':False,'LTO':True}
save(here/'candidates.json',result);print('Separate restart-workload candidates saved; existing preferred aliases unchanged.')
