#!/usr/bin/env python3
from common_segment import *
import re
record=json.loads((here/'build-summary.json').read_text())['records'];out={}
def functions(binary):
 s=run(['objdump','-d','--no-show-raw-insn',binary],text=True).stdout
 # Resolve unnamed CET PLT entries before comparing relocated call targets.
 plt={int(a,16)-4:n for a,n in re.findall(r'(?m)^\s*([0-9a-f]+):\s+jmp\s+\*[^\n]*#\s+[0-9a-f]+ <([^>]+@[^>]+)>',s)}
 s=re.sub(r'\b([0-9a-f]+) <_init\+0x[0-9a-f]+>',lambda m:m[1]+' <'+plt[int(m[1],16)]+'>' if int(m[1],16) in plt else m[0],s)
 c=re.split(r'(?m)^([0-9a-f]+) <([^>]+)>:\n',s);return {int(c[i],16):(c[i+1],c[i+2]) for i in range(1,len(c),3)}
def canon(addr,name,body):
 result=[]
 for l in body.splitlines():
  m=re.match(r'\s*[0-9a-f]+:\s*(.*)',l)
  if not m:continue
  s=re.sub(r'-?0x[0-9a-f]+\(%rip\)','RIP(%rip)',m[1]);s=re.sub(r'\b([0-9a-f]+) <([^>]+)>',lambda m:'LOCAL'+hex(int(m[1],16)-addr) if m[2].startswith(name) else '<'+re.sub(r'\.llvm\.\d+','.llvm.HASH',m[2])+'>',s);result.append(s)
 return '\n'.join(result)
def active(fs,initname,target):
 if target=='decompress_onepass':
  return next((a,n,b) for a,(n,b) in fs.items() if n.startswith(target) and '<mjpeg_fusion_mcu>' in b)
 init=next(b for n,b in fs.values() if n==initname or n.startswith(initname+'.'))
 addr=int(re.search(r'#\s+([0-9a-f]+) <'+target+r'(?:\.[A-Za-z_0-9.]+)?>',init)[1],16);n,b=fs[addr];return addr,n,b
for cc,r in record.items():
 assert sha(r['binary'])==r['sha256']
 for p,h in r['archives'].items():assert sha(p)==h
 old=functions(r['baseline_binary']);new=functions(r['binary']);d={}
 for label,init,target in [('entropy','jinit_huff_decoder','decode_mcu'),('coefficient','jinit_d_coef_controller','decompress_onepass')]:
  a=active(old,init,target);b=active(new,init,target);ca=canon(*a);cb=canon(*b)
  d[label]={'same_normalized_instructions':ca==cb,'old_sites':len(ca.splitlines()),'new_sites':len(cb.splitlines())}
  assert ca==cb,(cc,label)
  (W/(cc+'-'+label+'-original.asm')).write_text(a[2]);(W/(cc+'-'+label+'-candidate.asm')).write_text(b[2])
 native=next((addr,n,b) for addr,(n,b) in new.items() if n=='segment_data');(W/(cc+'-segment.asm')).write_text(native[2]);d['segment']={'instruction_sites':len(canon(*native).splitlines()),'fusion_call_sites':native[2].count('<mjpeg_fusion_mcu>'),'entropy_indirect_calls':'No indirect entropy callback in segment_data; direct local fast/slow routines.'}
 if json.loads((here/'build-summary.json').read_text()).get('packaging')=='original driver plus registration adapter':
  adapter=next(b for n,b in new.values() if n=='__wrap_mjpeg_fusion_begin')
  assert '<mjpeg_fusion_begin>' in adapter and '<mjpeg_segment_install>' in adapter
  assert any('<__wrap_mjpeg_fusion_begin>' in b for n,b in new.values() if n!='__wrap_mjpeg_fusion_begin')
  d['registration_adapter_verified']=True
 d['undefined_symbols']=run(['nm','-u',W/cc/'segment.o'],text=True).stdout
 out[cc]=d
run(['git','diff','--exit-code','--','src','simd']);save(here/'audit.json',out);print(json.dumps(out,indent=2))
