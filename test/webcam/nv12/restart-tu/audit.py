#!/usr/bin/env python3
from pathlib import Path
import sys,re
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
W=Path('/tmp/mjpeg-restart-tu');record=json.loads((here/'build-summary.json').read_text())['records'];out={}
def functions(binary):
 s=run(['objdump','-d','--no-show-raw-insn',binary],text=True).stdout;c=re.split(r'(?m)^([0-9a-f]+) <([^>]+)>:\n',s);return {int(c[i],16):(c[i+1],c[i+2]) for i in range(1,len(c),3)}
def canonical(addr,name,body):
 lines=[]
 for line in body.splitlines():
  m=re.match(r'\s*([0-9a-f]+):\s*(.*)',line)
  if not m:continue
  s=re.sub(r'-?0x[0-9a-f]+\(%rip\)','RIP(%rip)',m[2]);s=re.sub(r'\b([0-9a-f]+) <([^>]+)>',lambda m:'LOCAL'+hex(int(m[1],16)-addr) if m[2].startswith(name) else '<'+re.sub(r'\.llvm\.\d+','.llvm.HASH',m[2])+'>',s);lines.append(s)
 return '\n'.join(lines)
for cc in ('clang','gcc'):
 out[cc]={};baseline=None
 for label in ('control','layout','fast'):
  r=record[cc+'-tu-'+label];assert sha(r['binary'])==r['sha256']
  for p,h in r['archives'].items():assert sha(p)==h
  fs=functions(r['binary']);init=next(b for n,b in fs.values() if n=='jinit_huff_decoder');addr=int(re.search(r'#\s+([0-9a-f]+) <decode_mcu(?:\.llvm\.\d+)?>',init)[1],16);name,body=fs[addr];canon=canonical(addr,name,body)
  (W/(cc+'-'+label+'-ordinary.asm')).write_text(hex(addr)+' <'+name+'>:\n'+body)
  if label=='control':baseline=canon
  entry={'ordinary_symbol':name,'ordinary_instruction_sites':len(canon.splitlines()),'ordinary_code_matches_control':canon==baseline,'ordinary_canonical_sha256':hashlib.sha256(canon.encode()).hexdigest()}
  assert entry['ordinary_code_matches_control'],(cc,label,'original code generation changed')
  if label!='control':
   selector=next(b for n,b in fs.values() if n=='mjpeg_restart_select');native_addr=int(re.search(r'#\s+([0-9a-f]+) <decode_mcu>',selector)[1],16);native_name,native_body=fs[native_addr]
   assert not re.search(r'call.*<(?:memset|jzero_far)',native_body)
   (W/(cc+'-'+label+'-restart.asm')).write_text(hex(native_addr)+' <'+native_name+'>:\n'+native_body)
   entry['native_restart_instruction_sites']=len(canonical(native_addr,native_name,native_body).splitlines());entry['inline_retry_zeroing']=True
  if label=='fast':
   start=int(re.search(r'#\s+([0-9a-f]+) <start_pass_huff_decoder(?:\.llvm\.\d+)?>',init)[1],16);assert '<mjpeg_restart_select>' in fs[start][1]
   entry['scan_start_hook_verified']=True
  out[cc][label]=entry
 for lib in ('libjpeg.a','libturbojpeg.a'):
  raw=run(['ar','p',W/cc/lib,'jdhuff.c.o']).stdout
  if cc=='clang':
   ir=run(['llvm-dis-18','-o','-','-'],input=raw).stdout;assert b'ProfileSummary' not in ir and b'llvm.instrprof.' not in ir
  else:
   obj=W/'audit.o';obj.write_bytes(raw);opts=W/'audit-options.bin';run(['objcopy','--dump-section','.gnu.lto_.opts='+str(opts),obj]);assert b'-fprofile' not in opts.read_bytes() and b'-fauto-profile' not in opts.read_bytes()
 sections=run(['readelf','-S',W/cc/'restart.o'],text=True).stdout
 assert '.gnu.lto' not in sections and '.llvmbc' not in sections
 # No undefined references back into the original private/public entropy helpers.
 undefined=run(['nm','-u',W/cc/'restart.o'],text=True).stdout;assert not re.search(r'\b(?:jpeg_fill_bit_buffer|jpeg_huff_decode|jpeg_natural_order)\b',undefined)
 out[cc]['native_barrier']={'non_LTO':True,'renamed_slow_helpers':True,'object_sha256':sha(W/cc/'restart.o')}
run(['git','diff','--exit-code','--','src','simd']);save(here/'audit.json',{'pgo':False,'explicit_tune':False,'compilers':out});print(json.dumps(out,indent=2))
