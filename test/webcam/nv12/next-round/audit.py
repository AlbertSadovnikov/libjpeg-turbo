#!/usr/bin/env python3
from common import *
import re
summary={'pgo':False,'mtune':False,'modified_entropy_members':{},'native_objects':{}}
for cc in ('clang','gcc'):
 for name in ('diagnostic','span-off','control-word'):
  folder=WORK/(cc+'-'+name);record=json.loads((folder/'build.json').read_text())
  for filename,wanted in record['sha256'].items():assert sha(filename)==wanted,filename
  entry={}
  for lib in ('libjpeg.a','libturbojpeg.a'):
   raw=run(['ar','p',folder/lib,'jdhuff.c.o']).stdout
   if cc=='clang':
    ir=run(['llvm-dis-18','-o','-','-'],input=raw).stdout.decode();assert 'ProfileSummary' not in ir and 'llvm.instrprof.' not in ir
    entry[lib]='ThinLTO; no profile summary/instrumentation'
   else:
    tmp=WORK/'audit-object.o';tmp.write_bytes(raw);opts=WORK/'audit-options.bin'
    run(['objcopy','--dump-section','.gnu.lto_.opts='+str(opts),tmp]);options=opts.read_bytes();assert b'-fprofile' not in options and b'-fauto-profile' not in options
    assert b'-mtune=znver' not in options
    entry[lib]='GCC LTO; no profile flags; compiler default generic tuning'
  summary['modified_entropy_members'][cc+'-'+name]=entry
for name in ('control-wrapper','zero-wrapper','uv-control-wrapper','uv-paired-wrapper'):
 obj=WORK/(name+'.o');summary['native_objects'][name]=sha(obj)
for name in ('control','control-word','span-off','zero-groups'):
 binary=WORK/'bin'/('clang-'+name)
 text=run(['objdump','-d','--no-show-raw-insn',binary],text=True).stdout
 chunks=re.split(r'(?m)^([0-9a-f]+) <([^>]+)>:\n',text);functions={int(chunks[i],16):(chunks[i+1],chunks[i+2]) for i in range(1,len(chunks),3)}
 init=next(body for symbol,body in functions.values() if symbol=='jinit_huff_decoder')
 targets=re.findall(r'#\s+([0-9a-f]+) <decode_mcu(?:\.llvm\.\d+)?>',init);assert len(targets)==1
 addr=int(targets[0],16);symbol,body=functions[addr]
 (WORK/(name+'-active-entropy.asm')).write_text(hex(addr)+' <'+symbol+'>:\n'+body)
 summary.setdefault('clang_active_entropy',{})[name]={'symbol':symbol,'instruction_lines':sum(bool(re.match(r'\s*[0-9a-f]+:\s',line)) for line in body.splitlines()),'stack_operand_sites':sum(bool(re.search(r'\(%r(?:sp|bp)',line)) for line in body.splitlines()),'assembly_sha256':hashlib.sha256(body.encode()).hexdigest(),'identification':'Follow exported jinit_huff_decoder pointer, not first private name match.'}
for name in ('control-wrapper','zero-wrapper'):
 text=run(['objdump','-dr','--disassemble=mjpeg_fusion_mcu',WORK/(name+'.o')],text=True).stdout
 (WORK/(name+'-mcu.asm')).write_text(text)
 summary.setdefault('UV_dispatch',{})[name]={'assembly_sha256':hashlib.sha256(text.encode()).hexdigest(),'byte_size':int(next(line.split()[1] for line in run(['nm','-S',WORK/(name+'.o')],text=True).stdout.splitlines() if line.endswith(' mjpeg_fusion_mcu')),16)}
save(HERE/'audit.json',summary);print('Changed codec members audited for no PGO; active Clang entropy and native UV assembly retained.')
