#!/usr/bin/env python3
"""Map exact measured BMI machine code to source using a text-identical -g build."""
from pathlib import Path
import collections
import hashlib
import json
import re
import shutil
import subprocess
import sys

here=Path(__file__).resolve().parent
root=here.parents[2]
out=here/'instruction-audit'; out.mkdir(exist_ok=True)
base=Path('/tmp/mjpeg-stb-build/threshold-pair10')
source=Path('/tmp/mjpeg-stb-src/threshold-pair10')
temp=Path('/tmp/bmi-instruction-audit'); temp.mkdir(exist_ok=True)
def run(cmd,**kw): return subprocess.run(list(map(str,cmd)),check=True,capture_output=True,**kw)
def text_bytes(obj,label):
    path=temp/(label+'.text')
    run(['objcopy','-O','binary','--only-section=.text',obj,path])
    return path.read_bytes()
sites=[]; proof={}
variants=[('control',[]),('bmi2',['-mbmi2'])]
if '--explicit-shifts' in sys.argv:
    variants += [('explicit-shifts',['-mbmi2'])]
    out=here.parent/'bmi-intrinsics/explicit-shifts/audit'
    out.mkdir(parents=True,exist_ok=True)
if '--manual' in sys.argv:
    variants += [('bzhi-mask',['-mbmi2']),('extend-c',['-mbmi2']),
                 ('bextr-peek',['-mbmi','-mlzcnt','-mbmi2'])]
for name,flags in variants:
    input_source=source if name in ('control','bmi2') else Path('/tmp/mjpeg-intrinsics-src')/name
    obj=temp/(name+'.o')
    run(['cc','-O3','-g','-DNDEBUG','-I'+str(base),*flags,'-c',input_source/'src/jdhuff.c','-o',obj])
    measured=(base/'CMakeFiles/jpeg-static.dir/src/jdhuff.c.o') if name=='control' else (
        Path('/tmp/mjpeg-bmi-current-build/bmi2/matched-libjpeg.a/jdhuff.c.o') if name=='bmi2' else
        Path('/tmp/mjpeg-intrinsics-build')/name/'matched-libjpeg.a/jdhuff.c.o')
    code=text_bytes(obj,name+'-debug')
    assert code==text_bytes(measured,name+'-measured'),name+' debug code differs'
    proof[name]=dict(debug_text_identical=True,text_sha256=hashlib.sha256(code).hexdigest(),text_bytes=len(code))
    assembly=run(['objdump','-dlS','--no-show-raw-insn',obj],text=True).stdout
    (out/(name+'-source.asm')).write_text(assembly)
    plain=run(['objdump','-d','--no-show-raw-insn',obj],text=True).stdout
    function=''
    for line in plain.splitlines():
        m=re.match(r'^([0-9a-f]+) <([^>]+)>:',line)
        if m: function=m[2]
        m=re.match(r'^\s*([0-9a-f]+):\s+(shlx|shrx|sarx|bzhi|bextr|andn|lzcnt|tzcnt|blsr|pext|pdep|rorx)\s*(.*)',line)
        if not m: continue
        address,op,operands=m.groups()
        source_lines=run(['addr2line','-f','-i','-e',obj,'0x'+address],text=True).stdout.splitlines()
        stack=[dict(function=source_lines[i],location=source_lines[i+1]) for i in range(0,len(source_lines)-1,2)]
        functions=[s['function'] for s in stack]
        category='fast MCU' if 'decode_mcu_fast' in functions else 'slow MCU' if 'decode_mcu_slow' in functions else function
        sites.append(dict(variant=name,address='0x'+address,instruction=op,operands=operands,
                          function=function,category=category,inline_stack=stack))
    # Sampling binary keeps debug names but executes identical Huffman text.
    archive=temp/(name+'.a'); shutil.copyfile(base/'libjpeg.a',archive)
    member=temp/'jdhuff.c.o'; shutil.copyfile(obj,member)
    run(['ar','r',archive,member]); run(['ranlib',archive])
    binary=temp/('entropy-'+name)
    run(['c++','-O3','-g','-std=c++17','-I'+str(base),'-I'+str(source/'src'),
         '-I'+str(root/'benchmarks'),root/'test/webcam/cache-profile/driver.cc',
         '/tmp/mjpeg-google-bench/benchmarks/CMakeFiles/mjpeg-bench.dir/embedded_frame.cc.o',
         archive,'-lm','-o',binary])
    smoke=json.loads(run([binary,'entropy','2','1','0'],text=True).stdout)
    assert smoke['hash']=='feaf97b3b68cdc8c'
summary={}
for name,_ in variants:
    categories=collections.defaultdict(collections.Counter)
    for site in sites:
        if site['variant']==name: categories[site['category']][site['instruction']]+=1
    summary[name]={key:dict(value) for key,value in categories.items()}
(out/'summary.json').write_text(json.dumps(dict(proof=proof,counts_by_path=summary,sites=sites),indent=2)+'\n')
print(json.dumps(summary,indent=2))
