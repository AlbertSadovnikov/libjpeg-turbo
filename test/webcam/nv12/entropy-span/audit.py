#!/usr/bin/env python3
from pathlib import Path
import subprocess,json,re,hashlib
here=Path(__file__).resolve().parent;work=Path('/tmp/mjpeg-entropy-span');summary={'native_unprofiled_diagnostics':{},'actual_profiled_pipeline':{}}
def output(*c):return subprocess.check_output(list(map(str,c)),text=True)
for cc in ('clang','gcc'):
 for name in ('control','span'):
  obj=work/(cc+'-'+name+'-audit.o');asm=output('objdump','-drS',obj);(work/(cc+'-'+name+'-annotated.asm')).write_text(asm)
  symbols=[x.split() for x in output('nm','-S',obj).splitlines() if ' decode_mcu' in x]
  summary['native_unprofiled_diagnostics'][cc+'-'+name]={'decode_functions':{x[-1]:int(x[1],16) for x in symbols},'assembly_sha256':hashlib.sha256(asm.encode()).hexdigest(),'scope':'Native O3 -g unprofiled diagnostic object; not a timed object.'}
for name in ('control','span','selected'):
 binary=Path('/tmp/mjpeg-memset-call/nv12') if name=='selected' else work/name/'nv12'
 asm=output('objdump','-d','--no-show-raw-insn',binary)
 chunks=re.split(r'(?m)^([0-9a-f]+) <([^>]+)>:\n',asm)
 functions={int(chunks[i],16):(chunks[i+1],chunks[i+2]) for i in range(1,len(chunks),3)}
 init=next(body for symbol,body in functions.values() if symbol=='jinit_huff_decoder')
 addresses=re.findall(r'#\s+([0-9a-f]+) <decode_mcu(?:\.llvm\.\d+)?>',init)
 assert len(addresses)==1,(name,addresses)
 address=int(addresses[0],16);symbol,body=functions[address]
 (work/(name+'-active-decode.asm')).write_text(hex(address)+' <'+symbol+'>:\n'+body)
 size_line=next(x for x in output('nm','-S',binary).splitlines() if x.split()[0]==format(address,'016x') and x.split()[-1]==symbol)
 summary['actual_profiled_pipeline'][name]={'symbol':symbol,'address':hex(address),'bytes':int(size_line.split()[1],16),'static_stack_operand_sites':sum(bool(re.search(r'\(%r(?:sp|bp)',x)) for x in body.splitlines()),'scale8_metadata_byte_load_sites':{str(i):len(re.findall(r'movzbl\s+0x'+str(i)+r'\([^\n]*,8\)',body)) for i in (4,5,6,7)},'assembly_sha256':hashlib.sha256(body.encode()).hexdigest(),'selection':'Trace decode_mcu function pointer from exported jinit_huff_decoder; do not select first same-named private function.'}
(here/'assembly-audit.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
