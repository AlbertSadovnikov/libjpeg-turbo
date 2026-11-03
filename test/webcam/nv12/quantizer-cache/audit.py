#!/usr/bin/env python3
from pathlib import Path
import subprocess,json,re,hashlib
here=Path(__file__).resolve().parent;work=Path('/tmp/mjpeg-quantizer-cache');summary={}
for name in ('control','cached'):
 obj=work/(name+'.o');nm=subprocess.check_output(['nm','-S',str(obj)],text=True)
 ctx=next(x for x in nm.splitlines() if x.endswith(' _ZL3ctx'))
 asm=subprocess.check_output(['objdump','-dr',str(obj)],text=True);(work/(name+'-wrapper.asm')).write_text(asm)
 summary[name]={'context_bytes':int(ctx.split()[1],16),'wrapper_assembly_sha256':hashlib.sha256(asm.encode()).hexdigest()}
for name,obj,symbol in [('registers',Path('/tmp/mjpeg-coefficient-cost/registers.o'),'mjpeg_idct_ifast_registers'),('cached',work/'cached-kernel.o','mjpeg_idct_ifast_cached')]:
 asm=subprocess.check_output(['objdump','-d','--no-show-raw-insn','--disassemble='+symbol,str(obj)],text=True);(work/(name+'-kernel.asm')).write_text(asm)
 summary[name+'-kernel']={'quantizer_broadcast_instructions':asm.count('vbroadcasti128'),'instructions':sum(bool(re.match(r'\s*[0-9a-f]+:\s',x)) for x in asm.splitlines()),'assembly_sha256':hashlib.sha256(asm.encode()).hexdigest()}
assert summary['cached']['context_bytes']-summary['control']['context_bytes']==416
assert summary['registers-kernel']['quantizer_broadcast_instructions']==8
assert summary['cached-kernel']['quantizer_broadcast_instructions']==0
(here/'assembly-audit.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
