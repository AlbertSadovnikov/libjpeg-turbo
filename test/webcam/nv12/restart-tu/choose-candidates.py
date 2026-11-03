#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
r=json.loads((here/'build-summary.json').read_text())['records'];a=json.loads((here/'audit.json').read_text())['compilers'];b=json.loads((here/'balanced-summary.json').read_text());confirmation=json.loads((here/'confirm-summary.json').read_text());out={}
assert len(json.loads((here/'coefficients.json').read_text())['files'])==2325
for cc in ('clang','gcc'):
 v=r[cc+'-tu-fast'];assert sha(v['binary'])==v['sha256'];assert a[cc]['fast']['ordinary_code_matches_control']
 life=next(x for x in confirmation if x['compiler']==cc and 'Microsoft' in x['camera']);assert all(x['change_percent']<0 for x in life['brackets'])
 alias=Path('/tmp/mjpeg-restart-tu')/(cc+'-nv12')
 if alias.is_symlink():alias.unlink()
 assert not alias.exists();alias.symlink_to(v['binary'])
 out[cc]={'executable':str(alias),'target':v['binary'],'sha256':v['sha256'],'arguments':['fast','3','PASSES','JPEG...'],'contract':'Stock-fast-exact NV12 on tested inputs','core_LTO':True,'restart_TU_LTO':False,'PGO':False,'explicit_CPU_tune':False,'LifeCam_confirmation_change_percent':life['change_percent'],'Logitech_balanced_change_percent':b[cc]['candidate']['change_percent'],'status':'Preferred isolated restart prototype. Existing default aliases unchanged; short/sparse restart limits remain.'}
save(here/'candidates.json',out);print('Isolated restart candidate aliases saved; existing defaults unchanged.')
