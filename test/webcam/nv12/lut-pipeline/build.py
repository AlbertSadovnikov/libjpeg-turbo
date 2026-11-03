#!/usr/bin/env python3
"""Matched-object AC lookahead/unrolling experiments, with no PGO or LTO."""
from pathlib import Path
import difflib
import argparse
import hashlib
import json
import shutil
import subprocess

here=Path(__file__).resolve().parent;root=here.parents[3]
source=Path('/tmp/mjpeg-stb-src/threshold-pair10')
work=Path('/tmp/mjpeg-lut-pipeline');work.mkdir(exist_ok=True)
old=(source/'src/jdhuff.c').read_text()
manifest=json.loads((root/'test/webcam/bmi-intrinsics/pgo-lto/build-summary.json').read_text())
google=Path('/tmp/mjpeg-google-bench');common=Path('/tmp/mjpeg-pgo-lto')
def run(cmd):
    r=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
    if r.returncode:print(r.stderr,flush=True)
    r.check_returncode();return r
def raw(cmd):return subprocess.check_output(list(map(str,cmd)))
parser=argparse.ArgumentParser();parser.add_argument('--only',choices=['unroll2','pipeline2','carry','packed','metadata'])
args=parser.parse_args()
config=json.loads((here/'experiment.json').read_text()) if args.only and (here/'experiment.json').exists() else {}
isolation=json.loads((here/'isolation.json').read_text()) if args.only and (here/'isolation.json').exists() else {}
hit_start=old.index('        if (e.bits && k + e.step1 + e.step2 <= DCTSIZE2) {')
hit_end=old.index('        HUFF_DECODE_FAST(s, l, actbl);',hit_start)
hit=old[hit_start:hit_end]

def two_hit(early):
    preload='''          if (bits_left >= MJPEG_FUSED_BITS)
            next = fused[PEEK_BITS(MJPEG_FUSED_BITS)];
'''
    return '''        if (e.bits && k + e.step1 + e.step2 <= DCTSIZE2) {
          multi_entry next = { 0 };
          DROP_BITS(e.bits);
'''+(preload if early else '')+'''          k += e.step1 - 1;
          (*block)[jpeg_natural_order[k]] = e.value1;
          k += e.step2;
          (*block)[jpeg_natural_order[k]] = e.value2;
'''+('' if early else preload)+'''          /* The second peek reads only resident bits. It may inspect the
           * next block, but no bits/stores commit across this block boundary. */
          if (next.bits && k + 1 + next.step1 + next.step2 <= DCTSIZE2) {
            DROP_BITS(next.bits);
            k += next.step1;
            (*block)[jpeg_natural_order[k]] = next.value1;
            k += next.step2;
            (*block)[jpeg_natural_order[k]] = next.value2;
          }
          continue;
        }
'''

def carry():
    begin=old.index('      for (k = 1; k < DCTSIZE2; k++) {',old.index('LOCAL(boolean)\ndecode_mcu_fast'))
    end=old.index('\n    } else {',begin)
    return begin,end,'''      multi_entry e;
      FILL_BIT_BUFFER_FAST
      e = fused[PEEK_BITS(MJPEG_FUSED_BITS)];
      for (k = 1; k < DCTSIZE2;) {
        if (e.bits && k + e.step1 + e.step2 <= DCTSIZE2) {
          const int next_k = k + e.step1 + e.step2;
          multi_entry next = { 0 };
          DROP_BITS(e.bits);
          /* Launch the next lookup before finishing current coefficient
           * addressing/stores. Refill preserves the ordinary marker path. */
          if (next_k < DCTSIZE2) {
            FILL_BIT_BUFFER_FAST
            next = fused[PEEK_BITS(MJPEG_FUSED_BITS)];
          }
          k += e.step1 - 1;
          (*block)[jpeg_natural_order[k]] = e.value1;
          k += e.step2;
          (*block)[jpeg_natural_order[k]] = e.value2;
          k = next_k;
          e = next;
          continue;
        }
        HUFF_DECODE_FAST(s, l, actbl);
        r = s >> 4;
        s &= 15;
        if (s) {
          k += r;
          FILL_BIT_BUFFER_FAST
          r = GET_BITS(s);
          s = HUFF_EXTEND(r, s);
          (*block)[jpeg_natural_order[k]] = (JCOEF)s;
        } else {
          if (r != 15) break;
          k += 15;
        }
        k++;
        if (k < DCTSIZE2) {
          FILL_BIT_BUFFER_FAST
          e = fused[PEEK_BITS(MJPEG_FUSED_BITS)];
        }
      }
'''

def metadata():
    return '''        if (e.bits && k + e.step1 + e.step2 <= DCTSIZE2) {
          const multi_entry *next_entry = NULL;
          unsigned int next_bits = 0;
          DROP_BITS(e.bits);
          /* Fetch only the next entry's consumed-bit count early. Keep
           * coefficient payload loads after the current scatter stores. */
          if (bits_left >= MJPEG_FUSED_BITS) {
            next_entry = &fused[PEEK_BITS(MJPEG_FUSED_BITS)];
            next_bits = next_entry->bits;
          }
          k += e.step1 - 1;
          (*block)[jpeg_natural_order[k]] = e.value1;
          k += e.step2;
          (*block)[jpeg_natural_order[k]] = e.value2;
          if (next_bits) {
            multi_entry next = *next_entry;
            if (k + 1 + next.step1 + next.step2 <= DCTSIZE2) {
              DROP_BITS(next_bits);
              k += next.step1;
              (*block)[jpeg_natural_order[k]] = next.value1;
              k += next.step2;
              (*block)[jpeg_natural_order[k]] = next.value2;
            }
          }
          continue;
        }
'''

for compiler in ('gcc','clang'):
    control=manifest['builds'][compiler+'-base'];base=Path(control['build'])
    config[compiler+'-base']=control
    for kind in ([args.only] if args.only else ('unroll2','pipeline2','carry')):
        name=compiler+'-'+kind;tree=work/(name+'-source');build=work/name
        if tree.exists() or build.exists():raise FileExistsError(name)
        shutil.copytree(source,tree);build.mkdir()
        if kind=='carry':
            a,b,new=carry();text=old[:a]+new+old[b:]
        elif kind=='metadata':text=old[:hit_start]+metadata()+old[hit_end:]
        else:
            replacement=two_hit(kind in ('pipeline2','packed'))
            if kind=='packed':
                replacement=replacement.replace('          multi_entry next = { 0 };',
                    '          unsigned long long next_word = 0;\n          multi_entry next;')
                replacement=replacement.replace('            next = fused[PEEK_BITS(MJPEG_FUSED_BITS)];',
                    '            memcpy(&next_word, &fused[PEEK_BITS(MJPEG_FUSED_BITS)], sizeof(next_word));')
                marker='          /* The second peek reads only resident bits.'
                replacement=replacement.replace(marker,'''          /* Preserve one packed register across the current scatter stores.
           * The empty tied-register asm has no machine instructions, and
           * prevents premature scalarization of the future entry's fields. */
#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
          __asm__("" : "+r" (next_word));
#endif
          memcpy(&next, &next_word, sizeof(next));
'''+marker)
            text=old[:hit_start]+replacement+old[hit_end:]
        (tree/'src/jdhuff.c').write_text(text)
        (here/(name+'.patch')).write_text(''.join(difflib.unified_diff(old.splitlines(True),text.splitlines(True),fromfile='a/src/jdhuff.c',tofile='b/src/jdhuff.c')))
        records={}
        for lib in ('libjpeg.a','libturbojpeg.a'):
            objdir=build/(lib+'-objects');objdir.mkdir();obj=objdir/'jdhuff.c.o'
            extra=[] if lib=='libjpeg.a' else ['-DBMP_SUPPORTED','-DPNG_SUPPORTED','-DSPNG_STATIC','-DPPM_SUPPORTED']
            run([compiler,*control['flags'],'-mbmi2','-I'+str(base),*extra,'-c',tree/'src/jdhuff.c','-o',obj])
            shutil.copyfile(base/lib,build/lib);run(['ar','r',build/lib,obj]);run(['ranlib',build/lib])
            members=run(['ar','t',base/lib]).stdout.splitlines()
            changed=[m for m in members if raw(['ar','p',base/lib,m])!=raw(['ar','p',build/lib,m])]
            assert changed==['jdhuff.c.o'],changed
            records[lib]=dict(changed_members=changed,sha256=hashlib.sha256((build/lib).read_bytes()).hexdigest())
        binary=build/'nv12-sequence'
        run(['g++' if compiler=='gcc' else 'clang++','-fuse-ld=gold',*control['flags'],
             common/'sequence.o',common/'heldout-frame.o',google/'_deps/googlebenchmark-build/src/libbenchmark.a',
             build/'libjpeg.a',build/'libturbojpeg.a','-lm','-lpthread','-lrt','-o',binary])
        config[name]=dict(source=str(tree),build=str(build),flags=control['flags'],sequence_binary=str(binary))
        isolation[name]=records
        (here/'experiment.json').write_text(json.dumps(config,indent=2)+'\n')
        (here/'isolation.json').write_text(json.dumps(isolation,indent=2)+'\n')
        print(name,'built',flush=True)
