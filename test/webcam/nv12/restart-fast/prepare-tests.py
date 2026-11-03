#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
W=Path('/tmp/mjpeg-restart-fast');F=W/'fixtures';F.mkdir(exist_ok=True)
run(['gcc','-O2','-flto','-fuse-ld=gold','-I'+str(BASE/'gcc/stock'),'-I'+str(TREE/'src'),here/'fixtures.c',BASE/'gcc/stock/libjpeg.a','-lm','-o',W/'fixtures-tool'])
fixtures=[]
for label,source in [('ordinary',FRAMES[60]),*[(name,next(p for p in FIXTURES if p.stem==name)) for name in ('dense','zeroac','tail63')]]:
 for interval in (1,2,3,7,31,119,120,121,241,65535):
  p=F/f'{label}-rst{interval}.jpg';run([W/'fixtures-tool',source,p,interval,0]);fixtures.append(p)
 for interval in (3,120):
  p=F/f'{label}-optimized-rst{interval}.jpg';run([W/'fixtures-tool',source,p,interval,1]);fixtures.append(p)
# Marker fill bytes are legal before RST; add them in entropy-coded data only.
for label in ('ordinary','dense','zeroac'):
 src=F/f'{label}-rst3.jpg';data=src.read_bytes();pos=2
 while True:
  assert data[pos]==255;marker=data[pos+1];n=int.from_bytes(data[pos+2:pos+4],'big')
  if marker==0xda:pos+=2+n;break
  pos+=2+n
 prefix=data[:pos];body=data[pos:];changes=0
 for marker in range(0xd0,0xd8):
  old=bytes([255,marker]);new=bytes([255,255,255,marker]);changes+=body.count(old);body=body.replace(old,new)
 assert changes
 p=F/f'{label}-fill-rst3.jpg';p.write_bytes(prefix+body);fixtures.append(p)
save(here/'fixtures.json',{str(p):sha(p) for p in fixtures});print('Prepared',len(fixtures),'restart-interval/table/fill fixtures without pixel re-encoding.')
