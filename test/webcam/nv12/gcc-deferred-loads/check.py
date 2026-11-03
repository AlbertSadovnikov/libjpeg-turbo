#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
W=Path('/tmp/mjpeg-gcc-deferred-loads');B=WORK/'bin';record=json.loads((here/'build-summary.json').read_text())['records'];expected=json.loads((here.parent/'paired-fast-chroma/validation.json').read_text());extra=sorted(Path('/tmp/mjpeg-paired-fast-chroma').glob('independent-q*.jpg'))+[Path('/tmp/mjpeg-quantizer-cache')/f'changed-q{i}.jpg' for i in (1,2)]
validation={}
for name,r in record.items():
 cc=name.split('-')[0];validation[name]={}
 # Literal full arrays are checked against ordinary decoding inside each binary.
 capture=execute(r['binary'],'validate',*FRAMES);assert capture==expected[cc]['capture'];validation[name]['capture']=capture
 files=[*FIXTURES,*extra,FRAMES[60],*extra[::-1]]
 a=execute(B/(cc+'-uv-paired'),'validate',*files);b=execute(r['binary'],'validate',*files);assert a==b;validation[name]['mixed']=b
 print(name,'full capture, fallbacks and padding match.',flush=True)
save(here/'validation.json',validation)
# Literal coefficient/table equality on all captures plus fixtures/mutations.
obj=W/'coefficients.o';run(['g++','-O3','-DNDEBUG','-std=c++17',*INCLUDES,'-c',HERE.parent/'entropy-span/coefficients.cc','-o',obj])
for name,r in record.items():
 cc=name.split('-')[0];folder=W/name;cxx='clang++' if cc=='clang' else 'g++';lto='-flto=thin' if cc=='clang' else '-flto'
 run([cxx,lto,'-fuse-ld=gold',obj,folder/'libjpeg.a','-Wl,-u,__cpu_model','-lm','-o',W/(name+'-coefficients')])
coefficients=[]
for p in [*FRAMES,*FIXTURES,*extra]:
 reference=run([B/'gcc-reference-coefficients',p]).stdout
 for name in record:
  r=run([W/(name+'-coefficients'),p]);assert not r.stderr;assert r.stdout==reference,(name,p)
 coefficients.append({'file':str(p),'bytes':len(reference),'sha256':hashlib.sha256(reference).hexdigest()})
save(here/'coefficients.json',{'variants':list(record),'files':coefficients,'literal_equality':True});print('All literal coefficient streams match.',flush=True)
