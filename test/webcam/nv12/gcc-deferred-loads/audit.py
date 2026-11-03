#!/usr/bin/env python3
from pathlib import Path
import sys,re
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
W=Path('/tmp/mjpeg-gcc-deferred-loads');records=json.loads((here/'build-summary.json').read_text())['records'];out={}
def extract(binary):
 text=run(['objdump','-d','--no-show-raw-insn',binary],text=True).stdout;chunks=re.split(r'(?m)^([0-9a-f]+) <([^>]+)>:\n',text);f={int(chunks[i],16):(chunks[i+1],chunks[i+2]) for i in range(1,len(chunks),3)}
 init=next(b for n,b in f.values() if n=='jinit_huff_decoder');addr=int(re.search(r'#\s+([0-9a-f]+) <decode_mcu(?:\.llvm\.\d+)?>',init)[1],16);name,body=f[addr]
 canonical=[]
 for line in body.splitlines():
  m=re.match(r'\s*([0-9a-f]+):\s*(.*)',line)
  if not m:continue
  s=m[2];s=re.sub(r'(-?0x[0-9a-f]+)\(%rip\)','RIP(%rip)',s)
  s=re.sub(r'\b([0-9a-f]+) <([^>]+)>',lambda m:'LOCAL+'+hex(int(m[1],16)-addr) if m[2].startswith(name) else '<'+m[2]+'>',s)
  canonical.append(s)
 return body,'\n'.join(canonical)
original={cc:extract(WORK/'bin'/(cc+'-uv-paired'))[1] for cc in ('clang','gcc')}
control=None
for name,r in records.items():
 assert sha(r['binary'])==r['sha256']
 cc=name.split('-')[0]
 for p,h in r['archives'].items():
  assert sha(p)==h;raw=run(['ar','p',p,'jdhuff.c.o']).stdout
  if cc=='clang':
   ir=run(['llvm-dis-18','-o','-','-'],input=raw).stdout;assert b'ProfileSummary' not in ir and b'llvm.instrprof.' not in ir
  else:
   o=W/'audit.o';o.write_bytes(raw);opts=W/'audit-options.bin';run(['objcopy','--dump-section','.gnu.lto_.opts='+str(opts),o]);options=opts.read_bytes();assert b'-fprofile' not in options and b'-fauto-profile' not in options
   if name=='gcc-no-hoist':assert b'-fno-hoist-adjacent-loads' in options
 body,canonical=extract(r['binary']);(W/(name+'-entropy.asm')).write_text(body)
 if name=='gcc-control':control=canonical
 out[name]={'instruction_sites':len(canonical.splitlines()),'stack_operand_sites':len(re.findall(r'\(%r(?:sp|bp)',body)),'normalized_assembly_sha256':hashlib.sha256(canonical.encode()).hexdigest(),'same_as_original':canonical==original[cc],'same_as_gcc_control':canonical==control if cc=='gcc' else None,'canary': '%fs:0x28' in body,'endbr64':'endbr64' in body}
 assert cc!='gcc' or out[name]['canary']
run(['git','diff','--exit-code','--','src','simd']);save(here/'audit.json',out);print(json.dumps(out,indent=2))
