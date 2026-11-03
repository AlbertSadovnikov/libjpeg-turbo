#!/usr/bin/env python3
from pathlib import Path
import json,subprocess,hashlib,re,shlex
here=Path(__file__).resolve().parent;work=Path('/tmp/mjpeg-no-mtune');tmp=work/'audit';tmp.mkdir(exist_ok=True);summary={}
for compiler in ('clang','gcc'):
 summary[compiler]={}
 for name in ('stock','current'):
  build=work/compiler/name;commands=json.loads((build/'compile_commands.json').read_text())
  for command in commands:
   args=shlex.split(command['command'])
   assert not any(arg.startswith(x) for arg in args for x in ('-mtune','-march','-mcpu','-fprofile','-fauto-profile','-fcs-profile','--coverage'))
   if command['file'].endswith('.c'):assert any(arg.startswith('-flto') for arg in args)
  archives={}
  for lib in ('libjpeg.a','libturbojpeg.a'):
   archive=build/lib;members=subprocess.check_output(['ar','t',str(archive)],text=True).splitlines();lto=0;native=0;defaults=set()
   for member in members:
    raw=subprocess.check_output(['ar','p',str(archive),member])
    if compiler=='clang' and raw.startswith((b'BC\xc0\xde',b'\xde\xc0\x17\x0b')):
     ir=subprocess.check_output(['llvm-dis-18','-o','-','-'],input=raw).decode()
     assert 'ProfileSummary' not in ir and 'llvm.instrprof.' not in ir and '__llvm_prf_' not in ir,(compiler,name,lib,member)
     lto+=1
    elif compiler=='gcc':
     obj=tmp/'member.o';obj.write_bytes(raw)
     sections=subprocess.check_output(['readelf','-SW',str(obj)],text=True)
     if '.gnu.lto_' in sections:
      opts=tmp/'options.bin'
      subprocess.run(['objcopy','--dump-section','.gnu.lto_.opts='+str(opts),str(obj)],check=True,capture_output=True)
      options=opts.read_bytes()
      assert not any(x in options for x in (b'-fprofile',b'-fauto-profile',b'-fcs-profile',b'--coverage')),(compiler,name,lib,member)
      defaults.update(v.decode() for v in re.findall(rb'-mtune=[a-zA-Z0-9_-]+',options))
      # GCC serializes its ordinary -mtune=generic default even when the
      # invocation contains no -mtune. This is not an explicit tuning flag.
      assert all(v=='-mtune=generic' for v in defaults),defaults
      lto+=1
     else:native+=1
    else:native+=1
   assert lto>0
   archives[lib]={'members':len(members),'lto_members':lto,'native_members':native,'profiled_members':0,'compiler_default_tune_metadata':sorted(defaults),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
  symbols=subprocess.check_output(['nm',str(build/'nv12')],text=True)
  assert '__llvm_profile_' not in symbols and '__gcov_' not in symbols
  summary[compiler][name]=archives
  print(compiler,name,'audited: LTO, no PGO, no explicit CPU tuning.',flush=True)
(here/'audit.json').write_text(json.dumps({'pgo':False,'explicit_mtune':False,'cases':summary,'note':'GCC LTO option metadata includes the compiler default -mtune=generic. No -mtune/-march/-mcpu is passed in compile commands.'},indent=2)+'\n')
