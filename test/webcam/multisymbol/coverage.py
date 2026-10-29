#!/usr/bin/env python3
"""Untimed instrumented copies: count actual LUT hits on the embedded frame."""
from pathlib import Path
import json
import shutil
import subprocess
import tempfile

here=Path(__file__).resolve().parent
root=here.parents[2]
source=Path('/tmp/mjpeg-multisymbol-branchless-src')
c=(source/'src/jdhuff.c').read_text()
c=c.replace('#ifndef MJPEG_PAIR', '''static unsigned long long attempts, hits, pairs;
static void report_multi(void) {
  fprintf(stderr, "{\\"attempts\\":%llu,\\"hits\\":%llu,\\"pairs\\":%llu}\\n",
          attempts, hits, pairs);
}
#ifndef MJPEG_PAIR''',1)
c=c.replace('  JHUFF_TBL *h = cinfo->ac_huff_tbl_ptrs[tblno];', '''  static int registered;
  JHUFF_TBL *h = cinfo->ac_huff_tbl_ptrs[tblno];
  if (!registered) { atexit(report_multi); registered = 1; }''',1)
c=c.replace('        e = fused[PEEK_BITS(MJPEG_FUSED_BITS)];',
            '        attempts++;\n        e = fused[PEEK_BITS(MJPEG_FUSED_BITS)];',1)
c=c.replace('          DROP_BITS(e.bits);',
            '          hits++; pairs += e.count == 2;\n          DROP_BITS(e.bits);',1)
results={}
with tempfile.TemporaryDirectory(prefix='mjpeg-multi-coverage-') as tmp:
    tmp=Path(tmp)
    file=tmp/'jdhuff.c'
    file.write_text(c)
    for width in (8,10):
        build=Path(f'/tmp/mjpeg-multi{width}-branchless')
        subprocess.run(['cc','-O3','-DNDEBUG',f'-DMJPEG_FUSED_BITS={width}',
                        '-I'+str(build),'-I'+str(source/'src'),'-c',str(file),
                        '-o',str(tmp/'jdhuff.c.o')],check=True)
        archive=tmp/'libjpeg.a'
        shutil.copyfile(build/'libjpeg.a',archive)
        subprocess.run(['ar','r',str(archive),str(tmp/'jdhuff.c.o')],check=True)
        binary=tmp/'driver'
        subprocess.run(['c++','-O3','-std=c++17','-I'+str(build),'-I'+str(source/'src'),
                        '-I'+str(root/'benchmarks'),str(root/'test/webcam/cache-profile/driver.cc'),
                        '/tmp/mjpeg-google-bench/benchmarks/CMakeFiles/mjpeg-bench.dir/embedded_frame.cc.o',
                        str(archive),'-lm','-o',str(binary)],check=True)
        run=subprocess.run([str(binary),'entropy','1','1','0'],capture_output=True,text=True,check=True)
        result=json.loads(run.stderr)
        result['frames']=2
        result['note']='Counts cover fast-path AC iterations only, including one warmup frame.'
        results[str(width)]=result
(here/'coverage.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
