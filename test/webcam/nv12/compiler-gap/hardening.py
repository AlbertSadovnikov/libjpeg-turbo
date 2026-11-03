#!/usr/bin/env python3
from pathlib import Path
import sys,argparse,statistics
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
p=argparse.ArgumentParser();p.add_argument('action',choices=['build','run']);args=p.parse_args();W=Path('/tmp/mjpeg-compiler-gap');UV=Path('/tmp/mjpeg-paired-fast-chroma')
if args.action=='build':
 records={}
 for cc in ('clang','gcc'):
  folder=W/('hardened-'+cc);folder.mkdir(exist_ok=True);obj=folder/'jdhuff.c.o'
  flags=['-O3','-DNDEBUG','-mbmi2','-fno-lto','-fstack-protector-strong','-fcf-protection=full','-I'+str(BASE/'clang/current')]
  run([cc,*flags,'-c',TREE/'src/jdhuff.c','-o',obj])
  for lib in ('libjpeg.a','libturbojpeg.a'):
   shutil.copy2(BASE/'clang/current'/lib,folder/lib);run(['llvm-ar-18','r',folder/lib,obj]);run(['llvm-ranlib-18',folder/lib])
  b=link('clang','gap-hardened-'+cc,WORK/'uv-paired-wrapper.o',archives=folder,driver=UV/'driver.o',extra=[UV/'fast.o'])
  records[cc]={'flags':flags,'object_sha256':sha(obj),'matches_default_object':sha(obj)==sha(W/('entropy-'+cc)/'jdhuff.c.o'),'binary':str(b),'sha256':sha(b)}
 save(here/'hardening-build.json',records);print('Built explicit matched-hardening entropy objects.',flush=True);exit()
validation={}
for cc in ('clang','gcc'):
 b=WORK/'bin'/('clang-gap-hardened-'+cc)
 validation[cc]=execute(b,'validate',FRAMES[60],*FIXTURES,*sorted(UV.glob('independent-q*.jpg')))
assert validation['clang']==validation['gcc'];save(here/'hardening-validation.json',validation)
rows=[];brackets=[]
# Same host throughout: compare Clang defaults vs enabled protections, then
# compare both compilers with identical explicitly enabled protections.
for trial in range(3):
 for comparison in (('clang-default-vs-hardened','matched-hardening') if trial%2==0 else ('matched-hardening','clang-default-vs-hardened')):
  names=('clang','hardened-clang') if comparison=='clang-default-vs-hardened' else ('hardened-clang','hardened-gcc')
  group=[]
  for name in (names[0],names[1],names[0]):
   r=execute(WORK/'bin'/('clang-gap-'+name),'fast',3,6,*FRAMES[30:]);r.update(trial=trial,comparison=comparison,name=name);rows.append(r);group.append(r)
  assert len({r['hash'] for r in group})==1
  a=statistics.mean([group[0]['mean_ms'],group[2]['mean_ms']]);b=group[1]['mean_ms']
  brackets.append({'trial':trial,'comparison':comparison,'control_ms':a,'candidate_ms':b,'extra_ms':b-a,'change_percent':100*(b/a-1)})
  save(here/'hardening-results.json',{'records':rows,'brackets':brackets});print(brackets[-1],flush=True)
summary={}
for comparison in ('clang-default-vs-hardened','matched-hardening'):
 r=[v for v in brackets if v['comparison']==comparison];a=statistics.mean(v['control_ms'] for v in r);b=statistics.mean(v['candidate_ms'] for v in r)
 summary[comparison]={'control_ms':a,'candidate_ms':b,'extra_ms':b-a,'change_percent':100*(b/a-1),'brackets':r}
save(here/'hardening-summary.json',summary)
