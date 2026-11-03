#!/usr/bin/env python3
"""Link counters/stages against unchanged retained PGO/ThinLTO archives."""
from pathlib import Path
import subprocess,json,hashlib
here=Path(__file__).resolve().parent;root=here.parents[3]
work=Path('/tmp/mjpeg-coefficient-cost');work.mkdir(exist_ok=True)
fused=Path('/tmp/mjpeg-fused-chroma');base=Path('/tmp/mjpeg-pgo-lto/gcc-base')
info=json.loads((root/'test/webcam/bmi-intrinsics/pgo-lto/build-summary.json').read_text())['builds']['clang-pgo-lto']
def run(c):subprocess.run(list(map(str,c)),check=True)
includes=['-I'+str(base),'-I'+str(fused/'source/src'),'-I'+str(root/'test/webcam/nv12/fused-chroma')]
# Keep the reduced UV function and setup exactly as in the paired wrapper;
# only rename the unused reconstruction dispatcher to permit the probe hook.
run(['g++','-O3','-DNDEBUG','-std=c++17','-mavx2','-mfma',*includes,'-Dmjpeg_fusion_mcu=mjpeg_unused_fusion_mcu','-c','/tmp/mjpeg-paired-idct/paired.cc','-o',work/'fusion.o'])
run(['clang++','-O3','-DNDEBUG','-std=c++17',*includes,'-c',here/'probe.cc','-o',work/'probe.o'])
run(['clang++','-fuse-ld=gold',*info['flags'],work/'probe.o',work/'fusion.o','/tmp/mjpeg-paired-idct/pair.o',fused/'exact.o',fused/'pgo/libjpeg.a','-lm','-o',work/'probe'])
paths=[work/'probe',work/'probe.o',work/'fusion.o',Path('/tmp/mjpeg-paired-idct/pair.o'),fused/'pgo/libjpeg.a']
(here/'artifacts.json').write_text(json.dumps({'sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'codec_changes':[],'probe_flags':['-O3','-DNDEBUG','-std=c++17'],'wrapper_flags':['-O3','-DNDEBUG','-std=c++17','-mavx2','-mfma'],'link_flags':info['flags']},indent=2)+'\n')
