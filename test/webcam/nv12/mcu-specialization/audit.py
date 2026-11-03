#!/usr/bin/env python3
"""Code identity, source-order evidence and static register-pressure proxies."""
from pathlib import Path
import hashlib
import json
import re
import subprocess

here=Path(__file__).resolve().parent;work=Path('/tmp/mjpeg-mcu-specialization')
config=json.loads((here/'experiment.json').read_text());out=here/'audit';out.mkdir(exist_ok=True)
report={}
def run(cmd):return subprocess.check_output(list(map(str,cmd)),text=True)
for name,info in config.items():
    compiler=name.split('-')[0];base=Path(config[compiler+'-base']['build'])
    source=Path(info['source'])/'src/jdhuff.c';obj=work/(name+'-debug.o')
    subprocess.run([compiler,*info['flags'],'-mbmi2','-g','-I'+str(base),'-c',str(source),'-o',str(obj)],check=True)
    measured=work/(name+'-measured.o')
    measured.write_bytes(subprocess.check_output(['ar','p',str(Path(info['build'])/'libjpeg.a'),'jdhuff.c.o']))
    blobs=[]
    for label,path in [('debug',obj),('measured',measured)]:
        dest=work/(name+'-'+label+'.text')
        subprocess.run(['objcopy','-O','binary','--only-section=.text',str(path),str(dest)],check=True);blobs.append(dest.read_bytes())
    assert blobs[0]==blobs[1],name
    subprocess.run([compiler,*info['flags'],'-mbmi2','-g','-I'+str(base),'-S','-fverbose-asm',str(source),'-o',str(out/(name+'.s'))],check=True)
    assembly=run(['objdump','-dlS','--no-show-raw-insn','-Mintel',obj]);(out/(name+'.asm')).write_text(assembly)
    plain=run(['objdump','-d','--no-show-raw-insn','-Mintel',obj])
    functions={};fn=''
    for line in plain.splitlines():
        m=re.match(r'^([0-9a-f]+) <([^>]+)>:',line)
        if m:fn=m[2]
        if not fn.startswith('decode_mcu'):continue
        m=re.match(r'^\s*([0-9a-f]+):\s+([a-z][a-z0-9]*)\s*(.*)',line)
        if not m:continue
        r=functions.setdefault(fn,dict(instruction_sites=0,stack_operand_sites=0,stack_subtractions=[]))
        r['instruction_sites']+=1
        # RBP is a general register in these omit-frame-pointer builds.
        if re.search(r'\[(?:r|e)sp[+\]-]',m[3]):r['stack_operand_sites']+=1
        if m[2]=='sub' and m[3].startswith('rsp,'):r['stack_subtractions'].append(m[3])
    sizes={}
    for line in run(['nm','-S','--size-sort',measured]).splitlines():
        fields=line.split()
        if len(fields)==4 and fields[3].startswith('decode_mcu'):
            sizes[fields[3]]=int(fields[1],16)
    report[name]=dict(text_identical=True,text_sha256=hashlib.sha256(blobs[0]).hexdigest(),functions=functions,
                      decode_code_bytes=sizes,total_decode_code_bytes=sum(sizes.values()))
(out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
