#!/usr/bin/env python3
from pathlib import Path
import sys,re,collections
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
sys.path.insert(0,str(ROOT/'test/webcam/mjpeg-modes'));from capture import header
result=[]
for batch in sorted((ROOT/'test/webcam/mjpeg-modes/captures').glob('*')):
 if not (batch/'summary.json').exists():continue
 before=(batch/'before.txt').read_text();camera=re.search(r'Card type\s*:\s*(.*)',before)[1].strip();summary=json.loads((batch/'summary.json').read_text());groups={};signatures=set();total=0;rawbytes=0
 for path in sorted(batch.glob('*/manifest.json')):
  m=json.loads(path.read_text());raw=(path.parent/'capture.mjpg').read_bytes();assert len(raw)==m['raw_stream_bytes'];assert sha(path.parent/'capture.mjpg')==m['raw_stream_sha256']
  offset=0
  for f in m['frames']:
   data=(path.parent/f['file']).read_bytes();assert len(data)==f['bytes'];assert hashlib.sha256(data).hexdigest()==f['sha256'];assert f['stream_offset']==offset;assert raw[offset:offset+len(data)]==data;offset+=len(data)
   h=header(data);assert h==f['header'];assert h['precision']==8 and h['sof']=='0xc0';assert [(c['h'],c['v']) for c in h['components']]==[(2,1),(1,1),(1,1)]
   signatures.add(tuple(h['dht']));key=f"{h['width']}x{h['height']}";g=groups.setdefault(key,{'width':h['width'],'height':h['height'],'frames':[],'modes':[],'full_mcu_eligible':h['width']%16==0 and h['height']%8==0})
   g['frames'].append(str(path.parent/f['file']));total+=1
  assert offset==len(raw);rawbytes+=len(raw)
  g['modes'].append({'directory':str(path.parent),'requested':m['requested'],'negotiated':m['negotiated'],'observed_fps':m['observed_fps'],'sequence_gaps':m['sequence_gaps']})
 assert len(summary['modes'])==sum(len(g['modes']) for g in groups.values())
 result.append({'batch':batch.name,'camera':camera,'mode_count':len(summary['modes']),'frame_count':total,'bytes':rawbytes,'restored':summary['original_restored'],'original':json.loads((batch/'original.json').read_text()),'after':(batch/'after.txt').read_text(),'DHT_segment_hash_sets':[list(v) for v in sorted(signatures)],'sampling':'4:2:2','groups':groups})
save(here/'inventory.json',result)
for r in result:print(r['camera'],r['mode_count'],'modes',r['frame_count'],'frames',len(r['groups']),'sizes; hashes/buffer boundaries verified.')
