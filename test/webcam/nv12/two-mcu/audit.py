#!/usr/bin/env python3
from pathlib import Path
import sys,re
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
import argparse
p=argparse.ArgumentParser();p.add_argument("--paired-entry",action="store_true");args=p.parse_args()
TAG="two-mcu-pair" if args.paired_entry else "two-mcu"
PREFIX="paired-" if args.paired_entry else ""
W=Path('/tmp/mjpeg-two-mcu');record=json.loads((here/(PREFIX+'build-summary.json')).read_text());summary={}
for name,r in record['records'].items():
 if 'binary' in r:assert sha(r['binary'])==r['sha256'],name
 else:
  for path,wanted in r.items():assert sha(path)==wanted,path
for cc in ('clang','gcc'):
 summary[cc]={}
 for lib in ('libjpeg.a','libturbojpeg.a'):
  raw=run(['ar','p',W/(PREFIX+cc)/lib,'jdcoefct-8.c.o']).stdout
  if cc=='clang':
   ir=run(['llvm-dis-18','-o','-','-'],input=raw).stdout.decode();assert 'ProfileSummary' not in ir and 'llvm.instrprof.' not in ir
   assert 'target-cpu"="x86-64"' in ir
   summary[cc][lib]='ThinLTO; generic x86-64 controller; no profile summary/instrumentation'
  else:
   obj=W/'audit.o';obj.write_bytes(raw);opts=W/'audit-options.bin';run(['objcopy','--dump-section','.gnu.lto_.opts='+str(opts),obj]);options=opts.read_bytes().decode(errors='replace')
   assert '-fprofile' not in options and '-fauto-profile' not in options
   assert '-mtune=generic' in options and '-march=x86-64' in options
   summary[cc][lib]={'status':'GCC LTO; compiler default generic target; no profile flags','options':options}
 for name in (TAG+'-control',TAG):
  binary=WORK/'bin'/(cc+'-'+name);asm=run(['objdump','-d','--no-show-raw-insn',binary],text=True).stdout
  # Private names can repeat under ThinLTO. Save all onepass bodies, not a
  # misleading first-name match; the new query identifies the changed path.
  chunks=re.split(r'(?m)^([0-9a-f]+) <([^>]+)>:\n',asm)
  bodies=[chunks[i]+' <'+chunks[i+1]+'>:\n'+chunks[i+2] for i in range(1,len(chunks),3) if chunks[i+1].startswith('decompress_onepass')]
  assert bodies;out=W/(cc+'-'+name+'-controller.asm');out.write_text('\n'.join(bodies))
  summary[cc][name]={'assembly_sha256':sha(out),'bodies':len(bodies),'query_sites':sum(b.count('<mjpeg_two_mcu_active>') for b in bodies),'zeroing_sites':sum(b.count('vpxor') for b in bodies)}
save(here/(PREFIX+'audit.json'),summary);print('Controller hashes, no-PGO/LTO/default-target audits and assembly saved.')
