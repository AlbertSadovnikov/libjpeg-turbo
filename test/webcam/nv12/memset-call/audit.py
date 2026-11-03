#!/usr/bin/env python3
from pathlib import Path
import subprocess,re,json,hashlib
here=Path(__file__).resolve().parent;work=Path('/tmp/mjpeg-memset-call');summary={}
for name in ('control','direct-libc','inline','avx2'):
 binary=work/name/'nv12'
 text=subprocess.check_output(['objdump','-d','--no-show-raw-insn',str(binary)],text=True)
 # Both libjpeg and libturbojpeg contribute private functions of this name.
 # objdump --disassemble=name prints the first, which is NOT the active fused
 # controller. Select the one that actually calls the fusion dispatcher.
 chunks=re.split(r'(?m)^([0-9a-f]+) <([^>]+)>:\n',text)
 matches=[]
 for i in range(1,len(chunks),3):
  address,symbol,body=chunks[i:i+3]
  if symbol=='decompress_onepass' and '<mjpeg_fusion_mcu>' in body:matches.append((address,symbol,body))
 assert len(matches)==1,(name,len(matches));address,symbol,body=matches[0]
 (work/name/'active-controller.asm').write_text(address+' <'+symbol+'>:\n'+body)
 size_line=next(x for x in subprocess.check_output(['nm','-S',str(binary)],text=True).splitlines() if x.split()[0]==address)
 summary[name]={'active_controller_address':address,'controller_bytes':int(size_line.split()[1],16),'clear_call_targets':sorted(set(re.findall(r'call\s+\w+ <((?:jzero_far|memset)[^>]*)>',body))),'vector_stores':sum(bool(re.search(r'(?:v?mov\w*)\s+%[xy]mm\d+,.*\(',x)) for x in body.splitlines()),'static_stack_operand_sites':sum(bool(re.search(r'\(%r(?:sp|bp)',x)) for x in body.splitlines()),'assembly_sha256':hashlib.sha256(body.encode()).hexdigest()}
(here/'assembly-audit.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
