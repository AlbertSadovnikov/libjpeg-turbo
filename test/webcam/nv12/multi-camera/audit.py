#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
records=json.loads((here/'build-summary.json').read_text())['records']
for r in records.values():
 assert sha(r['binary'])==r['sha256']
 for p,h in r['archives'].items():assert sha(p)==h
for r in json.loads((here.parent/'next-round/selections.json').read_text()).values():assert sha(r['executable'])==r['sha256']
r=json.loads((here.parent/'gcc-deferred-loads/candidate.json').read_text());assert sha(r['executable'])==r['sha256']
run(['git','diff','--exit-code','--','src','simd'])
save(here/'audit.json',{'binaries_archives_hashes_verified':True,'previous_selections_unchanged':True,'production_src_simd_unchanged':True,'pgo':False,'explicit_tune':False,'notes':'Native support and codec archives unchanged; only geometry-aware drivers linked. Original compiler/default hardening configurations retained.'})
print('Archive/binary hashes and previous selections verified; production sources unchanged.')
