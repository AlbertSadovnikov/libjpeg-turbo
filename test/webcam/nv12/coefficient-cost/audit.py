#!/usr/bin/env python3
"""Static wrapper/kernel audit and local libc IFUNC implementation inspection."""
from pathlib import Path
import subprocess,json,ctypes,re,hashlib
here=Path(__file__).resolve().parent;work=Path('/tmp/mjpeg-coefficient-cost')
def output(*args):return subprocess.check_output(list(map(str,args)),text=True)
summary={'wrappers':{},'kernels':{}}
for cc in ('g++','clang++'):
 for name in ('control','layout','registers'):
  obj=work/(cc+'-'+name+'.o')
  asm=output('objdump','-dr','--disassemble=mjpeg_fusion_mcu',obj)
  (work/(cc+'-'+name+'-wrapper.asm')).write_text(asm)
  line=next(x for x in output('nm','-S',obj).splitlines() if x.endswith(' mjpeg_fusion_mcu'))
  text=work/(cc+'-'+name+'-text.bin');subprocess.run(['objcopy','--dump-section','.text='+str(text),str(obj)],check=True)
  summary['wrappers'][cc+'-'+name]={'dispatcher_bytes':int(line.split()[1],16),'static_stack_operand_sites':sum(bool(re.search(r'\(%r(?:sp|bp)',x)) for x in asm.splitlines()),'assembly_sha256':hashlib.sha256(asm.encode()).hexdigest(),'text_sha256':hashlib.sha256(text.read_bytes()).hexdigest()}
 for name in ('registers',):
  assert summary['wrappers'][cc+'-control']['text_sha256']==summary['wrappers'][cc+'-'+name]['text_sha256']
for name,path,symbol in [('control',Path('/tmp/mjpeg-paired-idct/pair.o'),'mjpeg_idct_ifast_pair'),('layout',work/'layout.o','mjpeg_idct_ifast_layout'),('registers',work/'registers.o','mjpeg_idct_ifast_registers')]:
 asm=output('objdump','-d','--disassemble='+symbol,path);(work/(name+'-kernel.asm')).write_text(asm)
 source=here/(name+'.asm') if name!='control' else here.parent/'paired-idct/pair.asm'
 plain=output('objdump','-d','--no-show-raw-insn','--disassemble='+symbol,path)
 text_bytes=int(next(x.split()[1] for x in output('size','-A',path).splitlines() if x.startswith('.text ')))
 summary['kernels'][name]={'instructions':sum(bool(re.match(r'\s*[0-9a-f]+:\s',x)) for x in plain.splitlines()),'text_bytes':text_bytes,'stack_operand_sites':sum('[wk(' in x for x in source.read_text().splitlines()),'assembly_sha256':hashlib.sha256(asm.encode()).hexdigest()}
# dlsym resolves memset's IFUNC in this diagnostic process. Inspect without
# ptrace, which the sandbox denies. Environment/CPU are the benchmark host's.
libc=ctypes.CDLL('libc.so.6');address=ctypes.cast(libc.memset,ctypes.c_void_p).value
raw=ctypes.string_at(address,512);(work/'memset.bin').write_bytes(raw)
asm=output('objdump','-D','-b','binary','-m','i386:x86-64',work/'memset.bin');(work/'resolved-memset.asm').write_text(asm)
mapping=next(x for x in Path('/proc/self/maps').read_text().splitlines() if int(x.split('-')[0],16)<=address<int(x.split('-')[1].split()[0],16))
parts=mapping.split();offset=address-int(parts[0].split('-')[0],16)+int(parts[2],16)
summary['libc_memset']={'path':parts[-1],'file_offset':hex(offset),'first_512_bytes_sha256':hashlib.sha256(raw).hexdigest(),'vector_stores_visible':bool(re.search(r'vmov\w*\s+%[xy]mm',asm)),'method':'ctypes/dlsym IFUNC resolution in diagnostic Python process, same host and environment; not ptrace of timed process'}
paired='/tmp/mjpeg-paired-idct/paired'
for name in ('decompress_onepass','jzero_far','decode_mcu'):
 if name=='decompress_onepass':
  # Two archives contribute same-named private functions. Select the active
  # fused controller; --disassemble=name only displays the first (unfused).
  chunks=re.split(r'(?m)^([0-9a-f]+) <([^>]+)>:\n',output('objdump','-d',paired))
  matches=[]
  for i in range(1,len(chunks),3):
   address,symbol,body=chunks[i:i+3]
   if symbol==name and '<mjpeg_fusion_mcu>' in body:matches.append(address+' <'+symbol+'>:\n'+body)
  assert len(matches)==1
  asm=matches[0]
 else:asm=output('objdump','-d','--disassemble='+name,paired)
 (work/(name+'.asm')).write_text(asm)
 summary[name]={'assembly_sha256':hashlib.sha256(asm.encode()).hexdigest()}
summary['controller_audit_correction']='2026-11-02: select active fusion-calling controller, not first same-named private function. ThinLTO already folds jzero_far into a direct memset call here. Timing records are unchanged.'
(here/'assembly-audit.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
