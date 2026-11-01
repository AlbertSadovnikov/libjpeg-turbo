#!/usr/bin/env python3
"""Recheck archive isolation after executable relinks, tests and benchmarks."""
from pathlib import Path
import hashlib
import json
import subprocess

here=Path(__file__).resolve().parent
base=Path('/tmp/mjpeg-stb-build/threshold-pair10')
source=Path('/tmp/mjpeg-stb-src/threshold-pair10/src/jdhuff.c')
def read_member(archive,member):
    return subprocess.check_output(['ar','p',str(archive),member])
def sha(data): return hashlib.sha256(data).hexdigest()
evidence=json.loads((here/'isolation.json').read_text())
checked=0
for lib in ('libjpeg.a','libturbojpeg.a'):
    members=subprocess.check_output(['ar','t',str(base/lib)],text=True).splitlines()
    original={name:sha(read_member(base/lib,name)) for name in members}
    for variant in ('bmi1-lzcnt','bmi2','bmi-all'):
        archive=Path('/tmp/mjpeg-bmi-current-build')/variant/lib
        assert sha(archive.read_bytes())==evidence[variant]['archives'][lib]['archive_sha256']
        assert subprocess.check_output(['ar','t',str(archive)],text=True).splitlines()==members
        changed=[name for name in members if sha(read_member(archive,name))!=original[name]]
        assert changed==['jdhuff.c.o'],(variant,lib,changed)
        checked+=len(members)-1
obj=Path('/tmp/bmi-current-generic-control.o')
subprocess.run(['cc','-I'+str(base),'-O3','-DNDEBUG','-c',str(source),'-o',str(obj)],check=True)
assert obj.read_bytes()==read_member(base/'libjpeg.a','jdhuff.c.o')
evidence['post_validation_archive_isolation_verified']=True
evidence['unchanged_members_rechecked']=checked
evidence['generic_control_rebuild_identical']=True
(here/'isolation.json').write_text(json.dumps(evidence,indent=2)+'\n')
print('Rechecked',checked,'unchanged member instances; generic control rebuild identical.')
