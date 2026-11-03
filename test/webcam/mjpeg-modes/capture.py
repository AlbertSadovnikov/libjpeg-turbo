#!/usr/bin/env python3
"""Enumerate real V4L2 MJPG modes and save unmodified per-buffer JPEGs."""
import argparse,datetime,hashlib,json,re,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent

def save(path,obj):path.write_text(json.dumps(obj,indent=2)+'\n')
def digest(data):return hashlib.sha256(data).hexdigest()
def modes(text):
 active=False;size=None;result=[];unsupported=[]
 for line in text.splitlines():
  m=re.search(r"\[\d+\]:\s+'([^']+)'",line)
  if m:active=m[1]=='MJPG';size=None
  if not active:continue
  m=re.search(r'Size: Discrete (\d+)x(\d+)',line)
  if m:size=tuple(map(int,m.groups()))
  elif 'Size:' in line:size=None;unsupported.append(line.strip())
  m=re.search(r'Interval: Discrete [\d.]+s \(([\d.]+) fps\)',line)
  if size and m:
   entry={'width':size[0],'height':size[1],'fps':m[1]}
   if entry not in result:result.append(entry)
  elif 'Interval:' in line and 'Discrete' not in line:unsupported.append(line.strip())
 return result,unsupported

def header(data):
 if data[:2]!=b'\xff\xd8':raise ValueError('buffer does not start with JPEG SOI')
 p=2;out={'dht':[],'dqt':[],'restart_interval':0}
 while p<len(data):
  if data[p]!=255:raise ValueError('invalid JPEG header marker')
  while p<len(data) and data[p]==255:p+=1
  if p>=len(data):raise ValueError('truncated JPEG marker')
  marker=data[p];p+=1
  if marker in (0xda,0xd9):break
  if marker==1 or 0xd0<=marker<=0xd8:continue
  n=int.from_bytes(data[p:p+2],'big')
  if n<2 or p+n>len(data):raise ValueError('truncated JPEG segment')
  payload=data[p+2:p+n];p+=n
  if marker in (0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf):
   if len(payload)<6 or len(payload)!=6+3*payload[5]:raise ValueError('invalid SOF')
   out.update(sof=hex(marker),precision=payload[0],height=int.from_bytes(payload[1:3],'big'),width=int.from_bytes(payload[3:5],'big'),components=[{'id':payload[i],'h':payload[i+1]>>4,'v':payload[i+1]&15,'quantizer':payload[i+2]} for i in range(6,len(payload),3)])
  if marker in (0xc4,0xdb):out['dht' if marker==0xc4 else 'dqt'].append(digest(payload))
  if marker==0xdd:
   if len(payload)!=2:raise ValueError('invalid DRI')
   out['restart_interval']=int.from_bytes(payload,'big')
 if 'width' not in out:raise ValueError('missing SOF')
 return out

def split(raw,log,count,dest,expected=None):
 entries=[(int(a),int(b),float(c)) for a,b,c in re.findall(r'cap dqbuf:.*?seq:\s*(\d+)\s+bytesused:\s*(\d+)\s+ts:\s*([\d.]+)',log)]
 if len(entries)<count:raise ValueError('capture log has fewer buffers than requested')
 entries=entries[-count:]
 if sum(e[1] for e in entries)!=len(raw):raise ValueError('buffer lengths do not reconstruct stream; raw data retained')
 offset=0;frames=[]
 for i,(seq,n,ts) in enumerate(entries):
  data=raw[offset:offset+n];info=header(data)
  if expected and (info['width'],info['height'])!=(expected['width'],expected['height']):raise ValueError('JPEG dimensions differ from requested mode')
  name=f'frame_{i:06d}.jpg'
  if dest:(dest/name).write_bytes(data)
  frames.append({'file':name,'device_sequence':seq,'timestamp_monotonic_seconds':ts,'stream_offset':offset,'bytes':n,'sha256':digest(data),'header':info});offset+=n
 gaps=sum(max(0,b[0]-a[0]-1) for a,b in zip(entries,entries[1:]))
 fps=(count-1)/(entries[-1][2]-entries[0][2]) if count>1 and entries[-1][2]>entries[0][2] else None
 return {'frames':frames,'frame_count':count,'raw_stream_bytes':len(raw),'raw_stream_sha256':digest(raw),'observed_fps':fps,'sequence_gaps':gaps,'inspection':'JPEG headers before first scan; no re-encoding or image decoding.'}

def original_mode(text,parm):
 size=re.search(r'Width/Height\s*:\s*(\d+)/(\d+)',text);fourcc=re.search(r"Pixel Format\s*:\s*'([^']+)'",text)
 fps=re.search(r'Frames per second:\s*[\d.]+\s*\((\d+)/(\d+)\)',parm)
 if not size or not fourcc or not fps:raise ValueError('cannot determine original format/fps; refusing mode changes without restoration metadata')
 return {'width':int(size[1]),'height':int(size[2]),'format':fourcc[1],'fps':int(fps[1])/int(fps[2])}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--device',default='/dev/video0');p.add_argument('--frames',type=int,default=12);p.add_argument('--skip',type=int,default=30);p.add_argument('--list-only',action='store_true');p.add_argument('--output',type=Path);a=p.parse_args()
 if a.frames<1 or a.skip<0:p.error('frames must be positive; skip must be nonnegative')
 if not Path(a.device).exists():p.exit(2,f'{a.device} is not exposed in this environment. Run this script from the host Linux terminal.\n')
 root=a.output or HERE/'captures'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');root.mkdir(parents=True,exist_ok=False)
 commands=[]
 def ctl(*args,timeout=20):
  cmd=['v4l2-ctl','-d',a.device,*map(str,args)];start=datetime.datetime.now(datetime.timezone.utc)
  try:
   r=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout)
   commands.append({'command':cmd,'started_utc':start.isoformat(),'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr});save(root/'commands.json',commands)
   r.check_returncode();return r.stdout+r.stderr
  except subprocess.TimeoutExpired as e:
   commands.append({'command':cmd,'started_utc':start.isoformat(),'timeout_seconds':timeout});save(root/'commands.json',commands);raise
 listing=ctl('--list-formats-ext');(root/'formats.txt').write_text(listing)
 plan,unsupported=modes(listing);save(root/'modes.json',{'device':a.device,'mjpg_modes':plan,'unhandled_nondiscrete_modes':unsupported})
 print(json.dumps({'directory':str(root),'mjpg_modes':plan,'unhandled_nondiscrete_modes':unsupported},indent=2),flush=True)
 if a.list_only:return 0
 if not plan:raise ValueError('no discrete MJPG modes enumerated')
 before=ctl('--all');(root/'before.txt').write_text(before)
 fmt=ctl('--get-fmt-video');parm=ctl('--get-parm');original=original_mode(fmt,parm);save(root/'original.json',original)
 outcomes=[];restored=False
 try:
  for mode in plan:
   folder=root/f"{mode['width']}x{mode['height']}-{mode['fps']}fps";folder.mkdir();result={'requested':mode,'directory':str(folder)}
   try:
    ctl(f"--set-fmt-video=width={mode['width']},height={mode['height']},pixelformat=MJPG",f"--set-parm={mode['fps']}")
    actual=ctl('--get-fmt-video','--get-parm');(folder/'negotiated.txt').write_text(actual)
    negotiated=original_mode(actual,actual)
    if negotiated['format']!='MJPG' or (negotiated['width'],negotiated['height'])!=(mode['width'],mode['height']):raise ValueError('driver negotiated a different format or size')
    timeout=max(20,(a.frames+a.skip)/float(mode['fps'])*3+10)
    log=ctl('--stream-mmap=4','--stream-poll',f'--stream-skip={a.skip}',f'--stream-count={a.frames}',f'--stream-to={folder}/capture.mjpg','--verbose',timeout=timeout)
    (folder/'capture.log').write_text(log);raw=(folder/'capture.mjpg').read_bytes();manifest=split(raw,log,a.frames,folder,mode)
    manifest.update(requested=mode,negotiated=negotiated,warmup_frames_discarded=a.skip,device=a.device);save(folder/'manifest.json',manifest)
    result.update(status='captured',frame_count=len(manifest['frames']),observed_fps=manifest['observed_fps'],headers=list({json.dumps(f['header'],sort_keys=True) for f in manifest['frames']}))
    print(folder.name,'captured',len(manifest['frames']),'frames',flush=True)
   except Exception as e:result.update(status='failed',error=str(e));print(folder.name,'FAILED',e,flush=True)
   outcomes.append(result);save(root/'summary.json',{'modes':outcomes,'original_restored':False})
 finally:
  try:
   ctl(f"--set-fmt-video=width={original['width']},height={original['height']},pixelformat={original['format']}",f"--set-parm={original['fps']:.12g}")
   after=ctl('--get-fmt-video','--get-parm');(root/'after.txt').write_text(after);now=original_mode(after,after)
   restored=all(now[k]==original[k] for k in ('width','height','format')) and abs(now['fps']-original['fps'])<0.001
  finally:save(root/'summary.json',{'modes':outcomes,'original_restored':restored})
 return 0 if restored and all(r['status']=='captured' for r in outcomes) else 1

if __name__=='__main__':
 try:sys.exit(main())
 except (ValueError,OSError,subprocess.SubprocessError) as e:sys.exit(str(e))
