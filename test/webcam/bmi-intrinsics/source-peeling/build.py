#!/usr/bin/env python3
"""Portable C loop peeling; change only affected objects in non-PGO archives."""
from pathlib import Path
import difflib
import argparse
import hashlib
import json
import shutil
import subprocess

here = Path(__file__).resolve().parent
source = Path('/tmp/mjpeg-stb-src/threshold-pair10')
prior = json.loads((here.parent / 'pgo-lto/build-summary.json').read_text())
work = Path('/tmp/mjpeg-source-peeling'); work.mkdir(exist_ok=True)
google = Path('/tmp/mjpeg-google-bench')
common = Path('/tmp/mjpeg-pgo-lto')
parser=argparse.ArgumentParser()
parser.add_argument('--only', choices=['huffman','idct','both','cold'])
args=parser.parse_args()
config = json.loads((here/'experiment.json').read_text()) if args.only and (here/'experiment.json').exists() else {}
isolation = json.loads((here/'isolation.json').read_text()) if args.only and (here/'isolation.json').exists() else {}
def run(cmd):
    return subprocess.run(list(map(str, cmd)), check=True, capture_output=True)
def sha(data):
    return hashlib.sha256(data).hexdigest()
for compiler in ('gcc', 'clang'):
    control = prior['builds'][compiler + '-base']
    config[compiler + '-base'] = control
    base = Path(control['build'])
    for kind in ([args.only] if args.only else ('huffman', 'idct', 'both')):
        name = compiler + '-' + kind
        tree = work / (name + '-source'); build = work / name
        if tree.exists() or build.exists(): raise FileExistsError(name)
        shutil.copytree(source, tree); build.mkdir()
        files = []
        if kind in ('huffman', 'both'):
            header = tree / 'src/jdhuff.h'
            old = '    while (prefix >= htbl->maxcode16[nb]) nb++; \\\n'
            new = '''    /* Peel three length checks; retain the general search. */ \\
    if (prefix >= htbl->maxcode16[nb]) { \\
      nb++; \\
      if (prefix >= htbl->maxcode16[nb]) { \\
        nb++; \\
        if (prefix >= htbl->maxcode16[nb]) { \\
          nb++; \\
          while (prefix >= htbl->maxcode16[nb]) nb++; \\
        } \\
      } \\
    } \\
'''
            text = header.read_text(); assert text.count(old) == 1
            header.write_text(text.replace(old, new)); files.append('src/jdhuff.h')
        if kind in ('idct', 'both'):
            path = tree / 'src/jdcoefct.c'; text = path.read_text()
            marker = '              for (xindex = 0; xindex < useful_width; xindex++) {\n'
            assert text.count(marker) == 1
            start = text.index(marker); body_start = start + len(marker)
            end = text.index('              }\n            }', body_start)
            body = text[body_start:end]
            replacement = ('              xindex = 0;\n'
                '              if (useful_width > 0) {\n' + body +
                '                for (xindex = 1; xindex < useful_width; xindex++) {\n' + body +
                '                }\n              }\n')
            text = text[:start] + replacement + text[end + len('              }\n'):]
            path.write_text(text); files.append('src/jdcoefct.c')
        if kind == 'cold':
            path=tree/'src/jdapistd.c';text=path.read_text()
            start=text.index('GLOBAL(JDIMENSION)\n_jpeg_read_raw_data')
            end=text.index('\n}\n',start)+3
            function=text[start:end]
            conditions=['cinfo->data_precision != BITS_IN_JSAMPLE','cinfo->master->lossless',
                'cinfo->global_state != DSTATE_RAW_OK','cinfo->output_scanline >= cinfo->output_height',
                'cinfo->progress != NULL','max_lines < lines_per_iMCU_row',
                'cinfo->coef->_decompress_data == NULL','!(*cinfo->coef->_decompress_data) (cinfo, data)']
            for condition in conditions:
                old='if ('+condition+')';assert function.count(old)==1
                function=function.replace(old,'if (MJPEG_UNLIKELY('+condition+'))')
            macro='''/* Layout hint for normal non-suspending raw decode; all checks remain. */
#if defined(__GNUC__) || defined(__clang__)
#define MJPEG_UNLIKELY(x) __builtin_expect(!!(x), 0)
#else
#define MJPEG_UNLIKELY(x) (x)
#endif
'''
            text=text[:start]+macro+function+'\n#undef MJPEG_UNLIKELY\n'+text[end:]
            path.write_text(text);files.append('src/jdapistd.c')
        patch = ''
        for file in files:
            patch += ''.join(difflib.unified_diff((source/file).read_text().splitlines(True),
                (tree/file).read_text().splitlines(True), fromfile='a/'+file, tofile='b/'+file))
        (here / (name + '.patch')).write_text(patch)
        record = {}
        for lib in ('libjpeg.a', 'libturbojpeg.a'):
            shutil.copyfile(base/lib, build/lib)
            members = run(['ar', 't', base/lib]).stdout.decode().splitlines()
            original = {m: sha(run(['ar', 'p', base/lib, m]).stdout) for m in members}
            extra = [] if lib == 'libjpeg.a' else ['-DBMP_SUPPORTED', '-DPNG_SUPPORTED', '-DSPNG_STATIC', '-DPPM_SUPPORTED']
            pairs = []
            if kind in ('huffman', 'both'): pairs.append(('src/jdhuff.c', 'jdhuff.c.o', ['-mbmi2']))
            if kind in ('idct', 'both'): pairs.append(('src/wrapper/jdcoefct-8.c', 'jdcoefct-8.c.o', []))
            if kind == 'cold': pairs.append(('src/wrapper/jdapistd-8.c','jdapistd-8.c.o',[]))
            for file, member, features in pairs:
                objdir = build / (lib + '-objects'); objdir.mkdir(exist_ok=True)
                obj = objdir / member
                run([compiler, *control['flags'], '-I'+str(base), *extra, *features,
                     '-c', tree/file, '-o', obj])
                run(['ar', 'r', build/lib, obj])
            run(['ranlib', build/lib])
            assert members == run(['ar', 't', build/lib]).stdout.decode().splitlines()
            changed = [m for m in members if original[m] != sha(run(['ar', 'p', build/lib, m]).stdout)]
            assert set(changed) <= {m for _,m,_ in pairs}
            record[lib] = dict(changed_members=changed, sha256=sha((build/lib).read_bytes()))
        binary = build / 'nv12-sequence'
        run(['g++' if compiler == 'gcc' else 'clang++', '-fuse-ld=gold', *control['flags'],
            common/'sequence.o', common/'heldout-frame.o', google/'_deps/googlebenchmark-build/src/libbenchmark.a',
            build/'libjpeg.a', build/'libturbojpeg.a', '-lm', '-lpthread', '-lrt', '-o', binary])
        config[name] = dict(source=str(tree), build=str(build), flags=control['flags'], sequence_binary=str(binary))
        isolation[name] = record
        (here/'experiment.json').write_text(json.dumps(config, indent=2)+'\n')
        (here/'isolation.json').write_text(json.dumps(isolation, indent=2)+'\n')
        print(name, record, flush=True)
