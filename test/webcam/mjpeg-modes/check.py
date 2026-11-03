#!/usr/bin/env python3
"""Exercise capture bookkeeping/restoration without opening a camera."""
import contextlib,importlib.util,io,json,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('capture_modes',HERE/'capture.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
root=HERE.parents[2];old=root/'test/webcam/20261023T230418Z'
# Real legacy stream verifies byte boundaries, hashes, metadata and timestamps.
manifest=m.split((old/'capture.mjpg').read_bytes(),(old/'capture.log').read_text(),120,None)
reference=json.loads((old/'manifest.json').read_text())
assert [f['sha256'] for f in manifest['frames']]==[f['sha256'] for f in reference['frames']]
assert manifest['frames'][0]['header']['width']==1920
assert [(c['h'],c['v']) for c in manifest['frames'][0]['header']['components']]==[(2,1),(1,1),(1,1)]
listing="""[0]: 'YUYV' (YUYV 4:2:2)
 Size: Discrete 640x480
  Interval: Discrete 0.033s (30.000 fps)
[1]: 'MJPG' (Motion-JPEG)
 Size: Discrete 1920x1080
  Interval: Discrete 0.033s (30.000 fps)
  Interval: Discrete 0.067s (15.000 fps)
"""
assert len(m.modes(listing)[0])==2
assert not m.modes("[0]: 'MJPG'\n Size: Stepwise 16x16 - 1920x1080\n")[0]
frames=[(old/f'frame_{i:06d}.jpg').read_bytes() for i in [1,2]]
with tempfile.TemporaryDirectory(prefix='mjpeg-capture-check-') as temp:
 t=Path(temp);device=t/'device';device.touch()
 for fail in [False,True]:
  state={'fps':'30','formats':0,'streams':0}
  output=t/('failed' if fail else 'success')
  def fake(cmd,**kwargs):
   stdout='';code=0
   for arg in cmd:
    if arg.startswith('--set-fmt-video='):state['formats']+=1
    if arg.startswith('--set-parm='):state['fps']=arg.split('=',1)[1]
   if '--list-formats-ext' in cmd:stdout=listing
   elif '--all' in cmd:stdout='Synthetic device state for test\n'
   elif '--get-fmt-video' in cmd or '--get-parm' in cmd:
    stdout=f"Format Video Capture:\n Width/Height : 1920/1080\n Pixel Format : 'MJPG'\nFrames per second: {state['fps']} ({int(float(state['fps']))}/1)\n"
   elif '--stream-poll' in cmd:
    state['streams']+=1
    if fail and state['streams']==1:code=1;stdout='simulated capture error'
    else:
     path=Path(next(c.split('=',1)[1] for c in cmd if c.startswith('--stream-to=')));path.write_bytes(b''.join(frames))
     stdout='cap dqbuf: 0 seq: 0 bytesused: 19 ts: 1.000 field: None\n'+''.join(f'cap dqbuf: {i} seq: {i+1} bytesused: {len(f)} ts: {2+i/30:.6f} field: None\n' for i,f in enumerate(frames))
   return subprocess.CompletedProcess(cmd,code,stdout,'')
  with patch.object(sys,'argv',['capture.py','--device',str(device),'--frames','2','--skip','1','--output',str(output)]),patch.object(m.subprocess,'run',side_effect=fake),contextlib.redirect_stdout(io.StringIO()):
   status=m.main()
  result=json.loads((output/'summary.json').read_text());assert result['original_restored'];assert state['fps']=='30';assert state['formats']==3
  assert status==(1 if fail else 0)
  assert result['modes'][0]['status']==('failed' if fail else 'captured')
  assert result['modes'][1]['status']=='captured'
print('PASS: original 120-buffer reconstruction; format parser; raw captures; restoration after success and capture failure.')
