#!/usr/bin/env python3
from pathlib import Path
import json
import subprocess
import sys

here=Path(__file__).resolve().parent
commands=[]
for name in ('defer-drop','left64','variable-refill','prefix4','dc-dispatch','dc-lite'):
    if '--only' in sys.argv and name not in sys.argv[sys.argv.index('--only')+1:]: continue
    source=Path('/tmp/mjpeg-zen-src')/name
    build=Path('/tmp/mjpeg-zen-build')/name
    for kind,cmd in [('configure',['cmake','-S',str(source),'-B',str(build),
                                  '-DCMAKE_BUILD_TYPE=Release','-DENABLE_SHARED=OFF','-DBUILD=20261024']),
                     ('build',['cmake','--build',str(build),'-j','6'])]:
        with (here/f'{name}-{kind}.log').open('w') as log:
            subprocess.run(cmd,stdout=log,stderr=log,check=True)
        commands.append(cmd)
    print(name,'built',flush=True)
destination=here
if '--only' in sys.argv:
    destination=here/('confirmation-'+'-'.join(sys.argv[sys.argv.index('--only')+1:]))
    destination.mkdir(exist_ok=True)
(destination/'build-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
