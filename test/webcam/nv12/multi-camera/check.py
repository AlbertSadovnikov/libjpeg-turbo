#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
B=WORK/'bin';inventory=json.loads((here/'inventory.json').read_text());records=[]
for camera in inventory:
 for size,g in camera['groups'].items():
  files=g['frames'];row={'batch':camera['batch'],'camera':camera['camera'],'size':size,'frames':len(files),'full_mcu_eligible':g['full_mcu_eligible'],'cases':{}}
  try:
   exacts={}
   for cc in ('clang','gcc'):
    stock=execute(B/(cc+'-camera-stock'),'validate',1,*files)
    exact=execute(B/(cc+'-camera-exact'),'validate',*files)
    fast=next(r for r in exact['cases'] if r['idct']=='fast' and r['mode']==3)
    assert fast['output_hash']==stock['hash'],(cc,camera['camera'],size,'stock-fast mismatch')
    assert fast['Y']['max_abs']==0 and fast['UV_vs_same_idct']['max_abs']==0
    row['cases'][cc]={'stock':stock,'exact':exact};exacts[cc]=exact
   assert next(r['output_hash'] for r in exacts['clang']['cases'] if r['idct']=='fast' and r['mode']==3)==next(r['output_hash'] for r in exacts['gcc']['cases'] if r['idct']=='fast' and r['mode']==3)
   deferred=execute(B/'gcc-camera-deferred','validate',*files);assert deferred==exacts['gcc'];row['gcc_deferred_matches']=True
   row['status']='passed'
  except Exception as e:
   row.update(status='failed',error=str(e));records.append(row);save(here/'validation.json',records);raise
  records.append(row);save(here/'validation.json',records);print(camera['batch'],size,len(files),'frames: stock-fast-exact, GCC rewrite, all modes and padding passed.',flush=True)
