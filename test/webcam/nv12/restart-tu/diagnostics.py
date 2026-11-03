#!/usr/bin/env python3
from pathlib import Path
import sys,argparse
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
p=argparse.ArgumentParser();p.add_argument('action',choices=['build','run']);args=p.parse_args();W=Path('/tmp/mjpeg-restart-tu')
if args.action=='build':
 source=(W/'clang/restart.c').read_text();diag='extern unsigned long long mjpeg_diag[11];\n#define JHIT(i) (++mjpeg_diag[i])\n'+source
 diag=diag.replace('decode_mcu_fast(j_decompress_ptr cinfo, JBLOCKROW *MCU_data)\n{','decode_mcu_fast(j_decompress_ptr cinfo, JBLOCKROW *MCU_data)\n{\n  JHIT(0);').replace('decode_mcu_slow(j_decompress_ptr cinfo, JBLOCKROW *MCU_data)\n{','decode_mcu_slow(j_decompress_ptr cinfo, JBLOCKROW *MCU_data)\n{\n  JHIT(8);')
 diag=diag.replace('if (!decode_mcu_fast(cinfo, MCU_data)) {','if (!decode_mcu_fast(cinfo, MCU_data)) {\n        JHIT(7);')
 diag=diag.replace('    bit_buf_type word, inverted; \\', '    JHIT(4); \\\n    bit_buf_type word, inverted; \\').replace('      get_buffer = (get_buffer << 48)', '      JHIT(5); \\\n      get_buffer = (get_buffer << 48)').replace('      GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE \\', '      JHIT(6); \\\n      GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE \\',1)
 diag=diag.replace('    if (c1 != 0) { \\', '    if (c1 == 0) JHIT(9); \\\n    if (c1 != 0) { \\\n      JHIT(10); \\').replace('if (e.bits && next_k <= DCTSIZE2) {','if (e.bits && next_k <= DCTSIZE2) {\n          JHIT(e.step2 ? 2 : 1);')
 diag=diag.replace('          continue;\n        }\n        HUFF_DECODE_FAST(s, l, actbl);','          continue;\n        }\n        JHIT(3);\n        HUFF_DECODE_FAST(s, l, actbl);')
 (W/'clang/restart-diag.c').write_text(diag)
 flags=json.loads((here/'build-summary.json').read_text())['records']['clang-sources']['native_flags']
 run(['clang',*flags,'-c',W/'clang/restart-diag.c','-o',W/'clang/restart-diag.o'])
 binary=link('clang','tu-diagnostic',WORK/'probe-fusion.o',archives=W/'clang',driver=WORK/'probe.o',extra=[W/'clang/restart-diag.o'])
 save(here/'diagnostic-build.json',{'binary':str(binary),'sha256':sha(binary),'source_sha256':sha(W/'clang/restart-diag.c'),'scope':'Untimed native restart TU only; ordinary original decoder is deliberately uninstrumented.'});exit()
keys=['fast_attempts','single_hits','pair_hits','fused_fallbacks','bulk_refills','clean_refills','ff_guard_refills','marker_retries','slow_calls','stuffed_ff','marker_observations'];sets=[]
for c in json.loads((HERE.parent/'multi-camera/inventory.json').read_text()):
 mode=max(c['groups']['1920x1080']['modes'],key=lambda m:float(m['requested']['fps']));sets.append((c['camera'],sorted(Path(mode['directory']).glob('frame_*.jpg'))))
sets += [(name,[Path('/tmp/mjpeg-restart-fast/fixtures')/name]) for name in ('zeroac-rst3.jpg','ordinary-fill-rst3.jpg')]
rows=[]
for name,files in sets:
 r=execute(WORK/'bin/clang-tu-diagnostic','count',*files);counts=dict(zip(keys,r['entropy_counters']))
 if 'Logitech' in name:assert not any(counts.values())
 else:assert counts['fast_attempts']+counts['slow_calls']-counts['marker_retries']==r['mcus']
 rows.append({'name':name,'frames':len(files),'mcus':r['mcus'],'counts':counts,'committed_restart_fast_percent':100*(counts['fast_attempts']-counts['marker_retries'])/r['mcus']});save(here/'diagnostics.json',rows);print(name,rows[-1]['committed_restart_fast_percent'],'% restart fast; retry count',counts['marker_retries'],flush=True)
