#!/usr/bin/env python3
"""BMI feature A/B on current winner, with all other archive members identical."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess

here=Path(__file__).resolve().parent
source=Path('/tmp/mjpeg-stb-src/threshold-pair10')
base=Path('/tmp/mjpeg-stb-build/threshold-pair10')
features={'bmi1-lzcnt':['-mbmi','-mlzcnt'],'bmi2':['-mbmi2'],
          'bmi-all':['-mbmi','-mlzcnt','-mbmi2']}
def run(cmd,**kw): return subprocess.run(list(map(str,cmd)),capture_output=True,check=True,**kw)
def digest(data): return hashlib.sha256(data).hexdigest()
commands=[]; evidence={}
original={}
for lib in ('libjpeg.a','libturbojpeg.a'):
    members=run(['ar','t',base/lib],text=True).stdout.splitlines()
    assert len(members)==len(set(members)), 'Duplicate member names need explicit handling'
    original[lib]={member:digest(run(['ar','p',base/lib,member]).stdout) for member in members}
    evidence[lib]={'members':len(members)}
for name,flags in features.items():
    tree=Path('/tmp/mjpeg-bmi-current-src')/name
    build=Path('/tmp/mjpeg-bmi-current-build')/name
    if tree.exists(): raise FileExistsError(tree)
    shutil.copytree(source,tree)
    cmake=tree/'CMakeLists.txt'
    cmake.write_text(cmake.read_text()+'\n# Experimental: Huffman decoder only.\n'
                     'set_property(SOURCE src/jdhuff.c APPEND PROPERTY COMPILE_OPTIONS '+ ' '.join(flags)+')\n')
    for label,cmd in [('configure',['cmake','-S',tree,'-B',build,'-DCMAKE_BUILD_TYPE=Release',
                                   '-DENABLE_SHARED=OFF','-DBUILD=20261024']),
                      ('build',['cmake','--build',build,'-j','6'])]:
        with (here/f'{name}-{label}.log').open('w') as log:
            subprocess.run(list(map(str,cmd)),stdout=log,stderr=log,check=True)
        commands.append(list(map(str,cmd)))
    evidence[name]={'flags':flags,'archives':{}}
    for lib in ('libjpeg.a','libturbojpeg.a'):
        objdir=build/('matched-'+lib); objdir.mkdir()
        obj=objdir/'jdhuff.c.o'
        extra=[] if lib=='libjpeg.a' else ['-DBMP_SUPPORTED','-DPNG_SUPPORTED','-DSPNG_STATIC','-DPPM_SUPPORTED']
        command=['cc','-I'+str(base),'-O3','-DNDEBUG',*extra,*flags,
                 '-c',str(source/'src/jdhuff.c'),'-o',str(obj)]
        run(command); commands.append(command)
        # Compile from the same absolute source path as the control, use the
        # same generated headers, then replace only this archive member.
        shutil.copyfile(base/lib,build/lib)
        run(['ar','r',build/lib,obj]); run(['ranlib',build/lib])
        actual_members=run(['ar','t',build/lib],text=True).stdout.splitlines()
        assert actual_members==list(original[lib])
        changed=[]
        for member,sha in original[lib].items():
            if digest(run(['ar','p',build/lib,member]).stdout)!=sha: changed.append(member)
        assert changed==['jdhuff.c.o'],(name,lib,changed)
        assembly=run(['objdump','-d',obj],text=True).stdout
        (here/f'{name}-{lib}.asm').write_text(assembly)
        ops={op:len(re.findall(r'^\s*[0-9a-f]+:\s+(?:[0-9a-f]{2}\s+)+\s*'+op+r'\b',assembly,re.M)) for op in
             ('shlx','shrx','sarx','bzhi','andn','lzcnt','tzcnt','blsr','pext','pdep')}
        evidence[name]['archives'][lib]=dict(changed_members=changed,
              identical_other_members=len(actual_members)-1,huffman_sha256=digest(obj.read_bytes()),
              archive_sha256=digest((build/lib).read_bytes()),static_instructions=ops)
    # Libraries are newer than their inputs, so only executable links rerun.
    with (here/f'{name}-relink.log').open('w') as log:
        subprocess.run(['cmake','--build',str(build),'-j','6'],stdout=log,stderr=log,check=True)
    for lib in ('libjpeg.a','libturbojpeg.a'):
        assert digest(run(['ar','p',build/lib,'jdhuff.c.o']).stdout)==evidence[name]['archives'][lib]['huffman_sha256']
        assert digest((build/lib).read_bytes())==evidence[name]['archives'][lib]['archive_sha256']
    print(name,'built; only Huffman archive members changed',flush=True)
(here/'isolation.json').write_text(json.dumps(evidence,indent=2)+'\n')
(here/'build-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
