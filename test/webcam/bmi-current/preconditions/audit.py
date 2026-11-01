#!/usr/bin/env python3
"""Compiler-precondition inspection only: these are not decode speed tests."""
from pathlib import Path
import collections
import json
import re
import subprocess

here=Path(__file__).resolve().parent
root=here.parents[3]
source=Path('/tmp/mjpeg-stb-src/threshold-pair10')
base=Path('/tmp/mjpeg-stb-build/threshold-pair10')
temp=Path('/tmp/bmi-preconditions'); temp.mkdir(exist_ok=True)
original=(source/'src/jdhuff.c').read_text()
def run(cmd,**kw): return subprocess.run(list(map(str,cmd)),check=True,capture_output=True,**kw)
def replace(s,old,new):
    assert s.count(old)==1,old[:70]
    return s.replace(old,new)
def functions(assembly):
    result=collections.defaultdict(list); name=''
    for line in assembly.splitlines():
        m=re.match(r'^([0-9a-f]+) <([^>]+)>:',line)
        if m: name=m[2]
        m=re.match(r'^\s*([0-9a-f]+):\s+([a-z][a-z0-9]*)\s*(.*)',line)
        if m: result[name].append(dict(address='0x'+m[1],mnemonic=m[2],operands=m[3]))
    return dict(result)
evidence={'probes':{},'real_kernel':{}}
for label,flags in [('generic',[]),('bmi2',['-mbmi2'])]:
    obj=temp/(label+'-probes.o')
    run(['cc','-O3','-DNDEBUG',*flags,'-c',here/'probes.c','-o',obj])
    assembly=run(['objdump','-d','--no-show-raw-insn','-Mintel',obj],text=True).stdout
    (here/(label+'-probes.asm')).write_text(assembly)
    evidence['probes'][label]=functions(assembly)
    for dialect in ('att','intel'):
        binary=temp/(label+'-'+dialect+'-checks')
        run(['cc','-O3','-DNDEBUG',*flags,'-masm='+dialect,here/'check.c','-o',binary])
        result=run([binary],text=True)
        evidence.setdefault('checks',{})[label+'-'+dialect]=result.stdout.strip()

for label in ('control','range-facts','noalias','aligned8','unsigned-mask'):
    c=original
    if label=='range-facts':
        start=c.index('decode_mcu_fast(j_decompress_ptr')
        before,fast=c[:start],c[start:]
        fast=replace(fast,'    if (s) {\n      FILL_BIT_BUFFER_FAST',
                     '    if (s) {\n      if ((unsigned int)s > 15) __builtin_unreachable();\n      FILL_BIT_BUFFER_FAST')
        fast=replace(fast,'        if (e.bits && k + e.step1 + e.step2 <= DCTSIZE2) {',
                     '''        if (e.bits && k + e.step1 + e.step2 <= DCTSIZE2) {
          if (e.bits > MJPEG_FUSED_BITS || e.step1 < 1 || e.step1 > 16 || e.step2 > 16)
            __builtin_unreachable();''')
        c=before+fast
    elif label=='noalias':
        start=c.index('decode_mcu_fast(j_decompress_ptr')
        before,fast=c[:start],c[start:]
        fast=replace(fast,'  JOCTET *buffer;','  JOCTET *__restrict buffer;')
        fast=replace(fast,'    JBLOCKROW block =','    JBLOCKROW __restrict block =')
        fast=replace(fast,'      const multi_entry *fused =','      const multi_entry *__restrict fused =')
        c=before+fast
    elif label=='aligned8':
        c=replace(c,'} multi_entry;','} multi_entry __attribute__((aligned(8)));')
    elif label=='unsigned-mask':
        pos=c.index('/*\n * Expanded entropy decoder object')
        c=c[:pos]+'''#undef GET_BITS
#define GET_BITS(n) ((int)(((unsigned int)(get_buffer >> (bits_left -= (n)))) & ((1U << (n)) - 1U)))

'''+c[pos:]
    src=temp/(label+'.c'); src.write_text(c)
    obj=temp/(label+'.o')
    run(['cc','-O3','-g','-DNDEBUG','-mbmi2','-I'+str(base),'-I'+str(source/'src'),'-c',src,'-o',obj])
    assembly=run(['objdump','-d','--no-show-raw-insn','-Mintel',obj],text=True).stdout
    (here/(label+'-kernel.asm')).write_text(assembly)
    sites=functions(assembly)
    counts=collections.Counter()
    for site in sites.get('decode_mcu',[]):
        if site['mnemonic'] not in ('shlx','shrx','sarx','bzhi','bextr','andn'): continue
        stack=run(['addr2line','-f','-i','-e',obj,site['address']],text=True).stdout.splitlines()
        if 'decode_mcu_fast' in stack: counts[site['mnemonic']]+=1
    # Read-only compiler inspection. Do not link the extra assumptions/restrict
    # into production until their call-site contracts have been established.
    evidence['real_kernel'][label]={'fast_mcu_bmi_sites':dict(counts),
                                   'decode_mcu_instruction_sites':len(sites.get('decode_mcu',[]))}
    if label in ('control','aligned8'):
        binary=temp/(label+'-layout')
        run(['cc','-O3','-DNDEBUG','-mbmi2','-I'+str(base),'-I'+str(source/'src'),
             '-DMJPEG_AUDIT_SOURCE="'+str(src)+'"',here/'layout.c',base/'libjpeg.a','-lm','-o',binary])
        evidence['real_kernel'][label]['layout']=json.loads(run([binary,root/'benchmarks/data/webcam_1920x1080_422.jpg'],text=True).stdout)
(here/'summary.json').write_text(json.dumps(evidence,indent=2)+'\n')
print(json.dumps({key:dict(value) for key,value in evidence['real_kernel'].items()},indent=2))
