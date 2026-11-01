#!/usr/bin/env python3
"""Configure/build retained isolated source trees; preserve exact commands."""
import json
from pathlib import Path
import subprocess

here=Path(__file__).resolve().parent
commands=[]
for name in ('compact9','compact-pair10','threshold-pair10'):
    source=Path('/tmp/mjpeg-stb-src')/name
    build=Path('/tmp/mjpeg-stb-build')/name
    width='9' if name=='compact9' else '10'
    configure=['cmake','-S',str(source),'-B',str(build),'-DCMAKE_BUILD_TYPE=Release',
               '-DENABLE_SHARED=OFF','-DBUILD=20261024','-DCMAKE_C_FLAGS=-DMJPEG_FUSED_BITS='+width]
    compile=['cmake','--build',str(build),'-j','6']
    for label,cmd in [('configure',configure),('build',compile)]:
        with (here/(name+'-'+label+'.log')).open('w') as log:
            subprocess.run(cmd,stdout=log,stderr=log,check=True)
        commands.append(cmd)
(here/'build-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
