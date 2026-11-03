#!/usr/bin/env python3
from common_segment import *
import argparse
p=argparse.ArgumentParser();p.add_argument("--registration-only",action="store_true");args=p.parse_args()
fixtures=[Path(p) for p in json.loads((HERE.parent/'restart-fast/fixtures.json').read_text())];inventory=json.loads((HERE.parent/'multi-camera/inventory.json').read_text());expected=json.loads((HERE.parent/'multi-camera/validation.json').read_text());reports=[];UV=Path('/tmp/mjpeg-paired-fast-chroma')
for c in inventory:
 for size,g in c['groups'].items():
  ref=next(r for r in expected if r['batch']==c['batch'] and r['size']==size)
  for cc in ('clang','gcc'):
   r=execute_segment(cc,True,'validate',*g['frames']);assert r==ref['cases'][cc]['exact'],(cc,c['camera'],size)
  reports.append({'batch':c['batch'],'size':size,'frames':len(g['frames']),'passed':True});save(here/'camera-validation.json',reports);print(c['batch'],size,'NV12/padding passed.',flush=True)
validation={}
for cc in ('clang','gcc'):
 validation[cc]={}
 for i,p in enumerate(fixtures):
  a=execute_segment(cc,False,'validate',p);b=execute_segment(cc,True,'validate',p);assert a==b,(cc,p);validation[cc][p.name]=b
  if i%10==9:print(cc,i+1,'restart fixtures passed.',flush=True)
 for size in ('640x480','1280x720','1920x1080'):
  files=[Path(c['groups'][size]['frames'][i]) for i in range(3) for c in inventory]
  assert execute_segment(cc,False,'validate',*files)==execute_segment(cc,True,'validate',*files)
 save(here/'fixture-validation.json',validation)
if args.registration_only:
 initial=json.loads((here/'initial-build-summary.json').read_text())['records'];current=json.loads((here/'build-summary.json').read_text())['records']
 for cc in ('clang','gcc'):assert initial[cc]['object_sha256']==current[cc]['object_sha256']
 assert len(json.loads((here/'coefficients.json').read_text())['files'])==2325
 print('Controller object byte-identical; existing 2,325 coefficient traces retained.',flush=True)
else:
 # Trace actual raw-controller MCUs; jpeg_read_coefficients alone would bypass
 # the new segment controller and would not establish local-state correctness.
 run(['g++','-O3','-DNDEBUG','-std=c++17',*INCLUDES,'-c',here/'trace.cc','-o',W/'trace.o'])
 for cc in ('clang','gcc'):
  cxx='clang++' if cc=='clang' else 'g++';lto='-flto=thin' if cc=='clang' else '-flto'
  run([cxx,lto,'-fuse-ld=gold',W/'trace.o',TU/cc/'restart.o',W/cc/'segment.o',TU/cc/'libjpeg.a','-Wl,-u,__cpu_model','-lm','-o',W/(cc+'-trace')])
 files=[Path(p) for c in inventory for g in c['groups'].values() for p in g['frames']]+fixtures+FRAMES+FIXTURES
 traces=[];selected={cc:0 for cc in ('clang','gcc')}
 for i,p in enumerate(files):
  reference=None;row={'file':str(p),'cases':{}}
  for cc,enabled in [('clang',False),('clang',True),('gcc',True)]:
   env=os.environ.copy();env['MJPEG_SEGMENT']='1' if enabled else '0';r=run([W/(cc+'-trace'),p],env=env);status=json.loads(r.stderr)
   if reference is None:reference=r.stdout
   else:assert r.stdout==reference,(cc,p)
   row['cases'][cc+('-segment' if enabled else '-control')]=status
   if enabled:selected[cc]+=status['selected']
  row.update(bytes=len(reference),sha256=hashlib.sha256(reference).hexdigest());traces.append(row)
  if i%300==299:save(here/'coefficients.json',{'literal_equality':True,'selected_frames':selected,'files':traces});print(i+1,'raw MCU coefficient traces passed.',flush=True)
 save(here/'coefficients.json',{'literal_equality':True,'selected_frames':selected,'files':traces})
# Same source-manager suspension test, with the actual new controller selected.
s=(HERE.parent/'two-mcu/check.cc').read_text().replace('two-MCU check failed','segment check failed')
s=s.replace('static boolean suspend','extern "C" int mjpeg_segment_enabled;\nextern "C" int mjpeg_segment_install(j_decompress_ptr);\nstatic boolean suspend')
needle=' const bool fused=mjpeg_fusion_begin(&c,r.uv.data(),up,3);';assert needle in s;s=s.replace(needle,needle)
s=s.replace('require(argc>=2);','require(argc>=2);const char *flag=std::getenv("MJPEG_SEGMENT");mjpeg_segment_enabled=!(flag&&std::strcmp(flag,"0")==0);')
(W/'suspend.cc').write_text(s);run(['g++','-O3','-DNDEBUG','-std=c++17',*INCLUDES,'-c',W/'suspend.cc','-o',W/'suspend.o'])
suspfiles=[FRAMES[60],*FIXTURES,*[p for p in fixtures if p.name in ('ordinary-rst2.jpg','ordinary-rst3.jpg','dense-rst2.jpg','dense-rst3.jpg','zeroac-rst3.jpg','zeroac-rst7.jpg','ordinary-fill-rst3.jpg','dense-fill-rst3.jpg','zeroac-fill-rst3.jpg','tail63-optimized-rst3.jpg')]]+[Path(c['groups'][size]['frames'][0]) for c in inventory for size in ('640x480','1280x720','1920x1080')]
result={}
for cc in ('clang','gcc'):
 cxx='clang++' if cc=='clang' else 'g++';lto='-flto=thin' if cc=='clang' else '-flto'
 binary=W/(cc+'-suspend');run([cxx,lto,'-fuse-ld=gold',W/'suspend.o',WORK/'uv-paired-wrapper.o',OLD_COMMON/'registers.o',OLD_COMMON/'exact.o',UV/'fast.o',TU/cc/'restart.o',W/cc/'segment.o',W/cc/'adapter.o','-Wl,--wrap=mjpeg_fusion_begin',TU/cc/'libjpeg.a','-Wl,-u,__cpu_model','-lm','-o',binary]);result[cc]={}
 for enabled in (False,True):
  env=os.environ.copy();env['MJPEG_SEGMENT']='1' if enabled else '0';r=run(['taskset','-c','0',binary,*suspfiles],text=True,env=env);assert not r.stderr;result[cc]['segment' if enabled else 'control']=json.loads(r.stdout)
 assert result[cc]['segment']['hash']==result[cc]['control']['hash'];assert result[cc]['segment']['suspensions']>0
 save(here/'suspension.json',result);print(cc,'forced suspension passed.',flush=True)
print('All segment-controller validation gates passed.',flush=True)
