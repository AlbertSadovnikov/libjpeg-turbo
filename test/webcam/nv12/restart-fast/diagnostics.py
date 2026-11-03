#!/usr/bin/env python3
from pathlib import Path
import sys,argparse
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
p=argparse.ArgumentParser();p.add_argument('action',choices=['build','run']);p.add_argument('--separate',action='store_true');args=p.parse_args();W=Path('/tmp/mjpeg-restart-fast')/('separate' if args.separate else '')
PREFIX='separate-' if args.separate else ''
TAG='rst-separate' if args.separate else 'rst'
if args.action=='build':
 source=(W/'clang/source/src/jdhuff.c').read_text();diag=source.replace('#include "jstdhuff.c"','#include "jstdhuff.c"\nextern unsigned long long mjpeg_diag[11];\n#define JHIT(i) (++mjpeg_diag[i])')
 diag=diag.replace('decode_mcu_fast(j_decompress_ptr cinfo, JBLOCKROW *MCU_data)\n{','decode_mcu_fast(j_decompress_ptr cinfo, JBLOCKROW *MCU_data)\n{\n  JHIT(0);').replace('decode_mcu_slow(j_decompress_ptr cinfo, JBLOCKROW *MCU_data)\n{','decode_mcu_slow(j_decompress_ptr cinfo, JBLOCKROW *MCU_data)\n{\n  JHIT(8);')
 if args.separate:
  diag=diag.replace('decode_mcu_restart_fast(j_decompress_ptr cinfo, JBLOCKROW *MCU_data)\n{','decode_mcu_restart_fast(j_decompress_ptr cinfo, JBLOCKROW *MCU_data)\n{\n  JHIT(0);')
  diag=diag.replace('if (!decode_mcu_restart_fast(cinfo, MCU_data)) {','if (!decode_mcu_restart_fast(cinfo, MCU_data)) {\n        JHIT(7);')
 diag=diag.replace('if (!decode_mcu_fast(cinfo, MCU_data)) {','if (!decode_mcu_fast(cinfo, MCU_data)) {\n        JHIT(7);')
 diag=diag.replace('    bit_buf_type word, inverted; \\', '    JHIT(4); \\\n    bit_buf_type word, inverted; \\').replace('      get_buffer = (get_buffer << 48)', '      JHIT(5); \\\n      get_buffer = (get_buffer << 48)').replace('      GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE \\', '      JHIT(6); \\\n      GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE \\',1)
 diag=diag.replace('    if (c1 != 0) { \\', '    if (c1 == 0) JHIT(9); \\\n    if (c1 != 0) { \\\n      JHIT(10); \\')
 diag=diag.replace('if (e.bits && next_k <= DCTSIZE2) {','if (e.bits && next_k <= DCTSIZE2) {\n          JHIT(e.step2 ? 2 : 1);')
 diag=diag.replace('          continue;\n        }\n        HUFF_DECODE_FAST(s, l, actbl);','          continue;\n        }\n        JHIT(3);\n        HUFF_DECODE_FAST(s, l, actbl);')
 patch(here/(PREFIX+'diagnostic.patch'),source,diag);folder=codec_variant('clang','restart-'+PREFIX+'diagnostic',diag)
 binary=link('clang',TAG+'-diagnostic',WORK/'probe-fusion.o',archives=folder,driver=WORK/'probe.o');save(here/(PREFIX+'diagnostic-build.json'),{'binary':str(binary),'sha256':sha(binary),'source_sha256':hashlib.sha256(diag.encode()).hexdigest(),'untimed_instrumentation_not_PGO':True});exit()
keys=['fast_attempts','single_hits','pair_hits','fused_fallbacks','bulk_refills','clean_refills','ff_guard_refills','marker_retries','slow_calls','stuffed_ff','marker_observations'];inventory=json.loads((HERE.parent/'multi-camera/inventory.json').read_text());rows=[]
filesets=[]
for c in inventory:
 mode=max(c['groups']['1920x1080']['modes'],key=lambda m:float(m['requested']['fps']))
 filesets.append((c['camera'],sorted(Path(mode['directory']).glob('frame_*.jpg'))))
filesets += [(name,[Path('/tmp/mjpeg-restart-fast/fixtures')/name]) for name in ('zeroac-rst3.jpg','zeroac-rst7.jpg','dense-rst2.jpg','ordinary-fill-rst3.jpg')]
for name,files in filesets:
 r=execute(WORK/'bin'/('clang-'+TAG+'-diagnostic'),'count',*files);counts=dict(zip(keys,r['entropy_counters']));assert counts['fast_attempts']+counts['slow_calls']-counts['marker_retries']==r['mcus']
 rows.append({'name':name,'frames':len(files),'mcus':r['mcus'],'counts':counts,'committed_fast_percent':100*(counts['fast_attempts']-counts['marker_retries'])/r['mcus']})
 save(here/(PREFIX+'diagnostics.json'),rows);print(name,counts,'committed fast %',rows[-1]['committed_fast_percent'],flush=True)
