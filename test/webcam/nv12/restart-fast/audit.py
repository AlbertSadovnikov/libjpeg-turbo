#!/usr/bin/env python3
from pathlib import Path
import sys,re
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
import argparse
p=argparse.ArgumentParser();p.add_argument("--separate",action="store_true");args=p.parse_args()
PREFIX="separate-" if args.separate else ""
TAG="rst-separate" if args.separate else "rst"
W=Path('/tmp/mjpeg-restart-fast')/('separate' if args.separate else '');records=json.loads((here/(PREFIX+'build-summary.json')).read_text())['records'];out={}
for name,r in records.items():
 if 'binary' not in r:continue
 assert sha(r['binary'])==r['sha256']
 for p,h in r['archives'].items():assert sha(p)==h
 cc=name.split('-')[0]
 if name.endswith('-fast'):
  for lib in ('libjpeg.a','libturbojpeg.a'):
   raw=run(['ar','p',W/cc/lib,'jdhuff.c.o']).stdout
   if cc=='clang':
    ir=run(['llvm-dis-18','-o','-','-'],input=raw).stdout;assert b'ProfileSummary' not in ir and b'llvm.instrprof.' not in ir
   else:
    obj=W/'audit.o';obj.write_bytes(raw);opts=W/'audit-options.bin';run(['objcopy','--dump-section','.gnu.lto_.opts='+str(opts),obj]);options=opts.read_bytes();assert b'-fprofile' not in options and b'-fauto-profile' not in options
 text=run(['objdump','-d','--no-show-raw-insn',r['binary']],text=True).stdout;chunks=re.split(r'(?m)^([0-9a-f]+) <([^>]+)>:\n',text);functions={int(chunks[i],16):(chunks[i+1],chunks[i+2]) for i in range(1,len(chunks),3)}
 init=next(b for n,b in functions.values() if n=='jinit_huff_decoder');address=int(re.search(r'#\s+([0-9a-f]+) <decode_mcu(?:\.llvm\.\d+)?>',init)[1],16);symbol,body=functions[address]
 if args.separate and name.endswith('-fast'):
  start_address=int(re.search(r'#\s+([0-9a-f]+) <start_pass_huff_decoder(?:\.llvm\.\d+)?>',init)[1],16)
  start_body=functions[start_address][1]
  restart_address=int(re.search(r'#\s+([0-9a-f]+) <decode_mcu_restart(?:\.llvm\.\d+)?>',start_body)[1],16)
  restart_symbol,restart_body=functions[restart_address]
  assert not re.search(r'call.*<(?:memset|jzero_far)',restart_body),name
  (W/(name+'-restart-entropy.asm')).write_text(hex(restart_address)+' <'+restart_symbol+'>:\n'+restart_body)
  out[name+'-restart-active']={'active_symbol':restart_symbol,'instruction_sites':sum(bool(re.match(r'\s*[0-9a-f]+:\s',l)) for l in restart_body.splitlines()),'no_out_of_line_clear':True,'selection':'Follow per-scan start_pass_huff_decoder assignment, not jinit default.'}
 # The constant 128-byte retry clear must stay inline; do not silently add
 # an out-of-line libc memset/jzero call to this path.
 assert not re.search(r'call.*<(?:memset|jzero_far)',body),name
 output=W/(name+'-entropy.asm');output.write_text(hex(address)+' <'+symbol+'>:\n'+body)
 out[name]={'active_symbol':symbol,'instruction_sites':sum(bool(re.match(r'\s*[0-9a-f]+:\s',l)) for l in body.splitlines()),'assembly_sha256':sha(output),'no_out_of_line_clear':True,'stack_canary':'%fs:0x28' in body}
 for n,b in functions.values():
  if n.startswith('decode_mcu_fast'):assert not re.search(r'call.*<(?:memset|jzero_far)',b),n
run(['git','diff','--exit-code','--','src','simd']);save(here/(PREFIX+'audit.json'),{'pgo':False,'explicit_tune':False,'entropy':out,'production_src_simd_unchanged':True});print('Archive hashes, no-PGO metadata and inline retry zeroing checked; assembly saved.')
