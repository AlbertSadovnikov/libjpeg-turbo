#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
import argparse
p=argparse.ArgumentParser();p.add_argument("--paired-entry",action="store_true");args=p.parse_args()
TAG="two-mcu-pair" if args.paired_entry else "two-mcu"
PREFIX="paired-" if args.paired_entry else ""
W=Path('/tmp/mjpeg-two-mcu');B=WORK/'bin';UV=Path('/tmp/mjpeg-paired-fast-chroma')
run(['gcc','-O2','-I'+str(BASE/'clang/current'),'-I'+str(TREE/'src'),here/'fixtures.c',BASE/'gcc/stock/libjpeg.a','-flto','-fuse-ld=gold','-lm','-o',W/'fixtures'])
extra=[]
for width,height in [(16,8),(48,24),(80,16)]:
 p=W/f'odd-{width}x{height}.jpg';run([W/'fixtures',p,width,height]);extra.append(p)
save(here/'fixture-hashes.json',{str(p):sha(p) for p in extra})
run(['g++','-O3','-DNDEBUG','-std=c++17',*INCLUDES,'-c',here/'check.cc','-o',W/'check.o'])
validation={}
quant=sorted(UV.glob('independent-q*.jpg'))+[Path('/tmp/mjpeg-quantizer-cache')/f'changed-q{i}.jpg' for i in (1,2)]
for cc in ('clang','gcc'):
 validation[cc]={}
 for label,files in [('capture',FRAMES),*[(p.stem,[p]) for p in FIXTURES],('mixed',[FRAMES[60],*quant,*FIXTURES,FRAMES[60]])]:
  a=execute(B/(cc+'-'+TAG+'-control'),'validate',*files);b=execute(B/(cc+'-'+TAG),'validate',*files);assert a==b,(cc,label)
  validation[cc][label]=b
 print(cc,'full NV12 contracts, fallbacks and padding match.',flush=True)
 # Smaller dedicated harness exercises actual input suspension and odd rows.
 cxx='clang++' if cc=='clang' else 'g++';lto='-flto=thin' if cc=='clang' else '-flto'
 reports=[]
 files=[FRAMES[60],*FIXTURES,*quant,*extra]
 for name,archives in [('control',BASE/cc/'current'),('candidate',W/(PREFIX+cc))]:
  binary=W/(cc+'-'+PREFIX+'check-'+name)
  run([cxx,'-O3',lto,'-fuse-ld=gold',W/'check.o',WORK/(TAG+'-wrapper.o'),OLD_COMMON/'registers.o',OLD_COMMON/'exact.o',UV/'fast.o',archives/'libjpeg.a','-Wl,-u,__cpu_model','-lm','-o',binary])
  reports.append(execute(binary,*files))
 assert reports[0]==reports[1],(cc,reports)
 assert reports[1]['suspensions']>0 and reports[1]['odd_resume_columns']>0
 validation[cc]['suspension_odd_rows']=reports
 print(cc,'suspended input and odd/one-MCU rows match literally.',flush=True)
save(here/(PREFIX+'validation.json'),validation)
