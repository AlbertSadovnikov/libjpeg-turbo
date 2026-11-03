#!/usr/bin/env python3
from pathlib import Path
import sys,re,collections
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
W=Path('/tmp/mjpeg-compiler-gap');summary={}
for cc in ('clang','gcc'):
 for label,binary in [('original',WORK/'bin'/(cc+'-uv-paired')),*[(e,WORK/'bin'/(cc+'-gap-'+e)) for e in ('clang','gcc')]]:
  text=run(['objdump','-d','--no-show-raw-insn',binary],text=True).stdout
  chunks=re.split(r'(?m)^([0-9a-f]+) <([^>]+)>:\n',text);functions={int(chunks[i],16):(chunks[i+1],chunks[i+2]) for i in range(1,len(chunks),3)}
  init=next(body for symbol,body in functions.values() if symbol=='jinit_huff_decoder')
  targets=re.findall(r'#\s+([0-9a-f]+) <decode_mcu(?:\.llvm\.\d+)?>',init);assert len(targets)==1
  addr=int(targets[0],16);symbol,body=functions[addr]
  sizes=run(['nm','-S',binary],text=True).stdout
  size=int(next(line.split()[1] for line in sizes.splitlines() if line.startswith(f'{addr:016x} ')),16)
  asm=W/(cc+'-'+label+'-entropy.asm');asm.write_text(hex(addr)+' <'+symbol+'>:\n'+body)
  ins=[l for l in body.splitlines() if re.match(r'\s*[0-9a-f]+:\s',l)]
  counts=collections.Counter(l.split(':',1)[1].strip().split()[0] for l in ins)
  summary[cc+'-'+label]={'binary':str(binary),'sha256':sha(binary),'active_address':hex(addr),'symbol':symbol,'bytes':size,'instruction_sites':len(ins),'stack_operand_sites':sum(bool(re.search(r'\(%r(?:sp|bp)',l)) for l in ins),'mnemonics':dict(counts),'calls':[l.strip() for l in ins if '\tcall' in l],'assembly_sha256':sha(asm)}
save(here/'assembly.json',summary)
print('Active entropy selected through jinit_huff_decoder; assembly saved.')
