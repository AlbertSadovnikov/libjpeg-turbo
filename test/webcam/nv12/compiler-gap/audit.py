#!/usr/bin/env python3
from pathlib import Path
import sys,re
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
W=Path('/tmp/mjpeg-compiler-gap');record=json.loads((here/'build-summary.json').read_text());out={'production_diff_empty':True,'pgo':False,'explicit_tune':False,'compiler_drivers':{},'hardened_assembly':{}}
for name,r in record['records'].items():
 if 'binary' in r:
  assert sha(r['binary'])==r['sha256']
  for p,h in r['archives'].items():assert sha(p)==h
 else:assert sha(W/('entropy-'+name)/'jdhuff.c.o')==r['object_sha256']
for cc,r in json.loads((here/'hardening-build.json').read_text()).items():
 assert sha(r['binary'])==r['sha256']
 text=run(['objdump','-d','--no-show-raw-insn',r['binary']],text=True).stdout
 # Both are native-object builds with one unambiguous baseline entropy symbol.
 chunks=re.split(r'(?m)^([0-9a-f]+) <([^>]+)>:\n',text)
 init=next(chunks[i+2] for i in range(1,len(chunks),3) if chunks[i+1]=='jinit_huff_decoder')
 target=re.search(r'#\s+([0-9a-f]+) <decode_mcu>',init)[1]
 body=next(chunks[i+2] for i in range(1,len(chunks),3) if int(chunks[i],16)==int(target,16))
 assert '%fs:0x28' in body and 'endbr64' in body
 (W/(cc+'-hardened-entropy.asm')).write_text(body)
 out['hardened_assembly'][cc]={'stack_canary':True,'endbr64':True,'sha256':hashlib.sha256(body.encode()).hexdigest()}
for cc in ('clang','gcc'):
 p=run([cc,'-###','-O3','-DNDEBUG','-mbmi2','-fno-lto','-c',TREE/'src/jdhuff.c'],text=True)
 out['compiler_drivers'][cc]=p.stderr
assert (BASE/'clang/current/jconfig.h').read_bytes()==(BASE/'gcc/current/jconfig.h').read_bytes()
assert (BASE/'clang/current/jconfigint.h').read_bytes()==(BASE/'gcc/current/jconfigint.h').read_bytes()
pair=json.loads((here.parent/'paired-fast-chroma/build-summary.json').read_text())
for cc in ('clang','gcc'):assert sha(WORK/'bin'/(cc+'-uv-paired'))==pair['binaries'][cc+'-uv-paired']
for r in json.loads((here.parent/'next-round/selections.json').read_text()).values():assert sha(r['executable'])==r['sha256']
run(['git','diff','--exit-code','--','src','simd']);save(here/'audit.json',out)
print('Binaries/archives/configs verified; both matched-hardening entropy bodies contain canaries and endbr64; selections unchanged.')
