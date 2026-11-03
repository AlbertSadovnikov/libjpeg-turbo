#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
record=json.loads((here/'build-summary.json').read_text())['records'];r=record['gcc-deferred'];assert sha(r['binary'])==r['sha256']
confirm=json.loads((here/'confirm-summary.json').read_text())['gcc-deferred'];assert all(b['change_percent']<0 for b in confirm['brackets'])
assert json.loads((here/'coefficients.json').read_text())['literal_equality']
alias=Path('/tmp/mjpeg-gcc-deferred-loads/nv12')
if alias.is_symlink():alias.unlink()
assert not alias.exists();alias.symlink_to(r['binary'])
save(here/'candidate.json',{'compiler':'gcc 13.3','executable':str(alias),'target':r['binary'],'sha256':r['sha256'],'arguments':['fast','3','PASSES','JPEG...'],'contract':'Stock-fast-exact NV12 on tested inputs; same runtime Huffman tables and quantizers.','status':'Retained separate GCC experiment; existing Clang/reduced selections unchanged.','pgo':False,'explicit_tune':False,'LTO':True})
print('Separate GCC candidate alias retained; previous selections unchanged.')
