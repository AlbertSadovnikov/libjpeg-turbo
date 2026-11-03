#!/usr/bin/env python3
"""Audit complete fresh archives, not just the final link command."""
from pathlib import Path
import json,subprocess,hashlib
here=Path(__file__).resolve().parent;work=Path('/tmp/mjpeg-lto-only');summary={}
for name in ('stock','current'):
 build=work/name;summary[name]={}
 for lib in ('libjpeg.a','libturbojpeg.a'):
  archive=build/lib;members=subprocess.check_output(['llvm-ar-18','t',str(archive)],text=True).splitlines();bitcode=0;native=0
  for member in members:
   raw=subprocess.check_output(['llvm-ar-18','p',str(archive),member])
   if raw.startswith((b'BC\xc0\xde',b'\xde\xc0\x17\x0b')):
    ir=subprocess.check_output(['llvm-dis-18','-o','-','-'],input=raw).decode()
    assert 'ProfileSummary' not in ir,(name,lib,member)
    assert 'llvm.instrprof.' not in ir,(name,lib,member)
    assert '__llvm_prf_' not in ir,(name,lib,member)
    bitcode+=1
   else:native+=1
  summary[name][lib]={'members':len(members),'thinlto_bitcode_members':bitcode,'native_members':native,'profile_summary_modules':0,'instrumented_modules':0,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
  assert bitcode>0
 commands=json.loads((build/'compile_commands.json').read_text())
 assert all('-fprofile' not in r['command'] for r in commands)
 assert all('-flto=thin' in r['command'] for r in commands if str(r['file']).endswith('.c'))
 symbols=subprocess.check_output(['nm',str(build/'nv12')],text=True)
 assert '__llvm_profile_' not in symbols
 print(name,'all archive members audited: ThinLTO enabled, no ProfileSummary/instrumentation.',flush=True)
(here/'no-pgo-audit.json').write_text(json.dumps({'pgo':False,'cases':summary},indent=2)+'\n')
