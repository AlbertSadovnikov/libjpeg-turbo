#!/usr/bin/env python3
"""Manual BMI candidates, matched archives, and reviewable source-only deltas."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import difflib
import argparse

here=Path(__file__).resolve().parent
root=here.parents[2]
base=Path('/tmp/mjpeg-stb-build/threshold-pair10')
source=Path('/tmp/mjpeg-stb-src/threshold-pair10')
features={'bzhi-mask':['-mbmi2'],'extend-c':['-mbmi2'],
          'bextr-peek':['-mbmi','-mlzcnt','-mbmi2'], 'explicit-shifts':['-mbmi2']}
parser=argparse.ArgumentParser()
parser.add_argument('--only', choices=list(features))
args=parser.parse_args()
if args.only: features={args.only:features[args.only]}
def run(cmd,**kw): return subprocess.run(list(map(str,cmd)),check=True,capture_output=True,**kw)
def sha(data): return hashlib.sha256(data).hexdigest()
original={}
for lib in ('libjpeg.a','libturbojpeg.a'):
    members=run(['ar','t',base/lib],text=True).stdout.splitlines()
    original[lib]={member:sha(run(['ar','p',base/lib,member]).stdout) for member in members}
isolation=json.loads((here/'isolation.json').read_text()) if args.only and (here/'isolation.json').exists() else {}
commands=[]
for name,flags in features.items():
    tree=Path('/tmp/mjpeg-intrinsics-src')/name
    build=Path('/tmp/mjpeg-intrinsics-build')/name
    if tree.exists(): raise FileExistsError(tree)
    shutil.copytree(source,tree)
    c=(tree/'src/jdhuff.c').read_text()
    if name=='explicit-shifts':
        pos=c.index('/*\n * Expanded entropy decoder object')
        c=c[:pos]+'''/* Explicit register shifts; same BMI2 target as the control.
 * SHRX/SHLX preserve flags. Keep 32-bit masks/sign math at 32 bits. */
static inline bit_buf_type mjpeg_shrx(bit_buf_type x, unsigned int n)
{
  bit_buf_type out, count = n;
  __asm__("shrx {%2, %1, %0|%0, %1, %2}" : "=r"(out) : "r"(x), "r"(count));
  return out;
}
static inline unsigned int mjpeg_shlx(unsigned int x, unsigned int n)
{
  unsigned int out;
  __asm__("shlx {%2, %1, %0|%0, %1, %2}" : "=r"(out) : "r"(x), "r"(n));
  return out;
}
#define MJPEG_SHLX(x, n) (__builtin_constant_p(n) ? ((x) << (n)) : mjpeg_shlx((x), (n)))
#undef GET_BITS
#undef PEEK_BITS
#define GET_BITS(n) (((int)mjpeg_shrx(get_buffer, bits_left -= (n))) & ((int)MJPEG_SHLX(1U, (n)) - 1))
#define PEEK_BITS(n) (((int)mjpeg_shrx(get_buffer, bits_left - (n))) & ((int)MJPEG_SHLX(1U, (n)) - 1))

'''+c[pos:]
        old='  ((x) + ((((x) - (1 << ((s) - 1))) >> 31) & (((NEG_1) << (s)) + 1)))'
        assert c.count(old)==1
        c=c.replace(old, '  ((x) + ((((x) - (int)MJPEG_SHLX(1U, (s) - 1)) >> 31) & (MJPEG_SHLX(NEG_1, (s)) + 1)))')
    elif name=='bzhi-mask':
        pos=c.index('/*\n * Expanded entropy decoder object')
        c=c[:pos]+'''#include <immintrin.h>
#undef GET_BITS
#define GET_BITS(n) ((int)_bzhi_u32((unsigned int)(get_buffer >> (bits_left -= (n))), (n)))

'''+c[pos:]
    elif name=='extend-c':
        old='''  ((x) + ((((x) - (1 << ((s) - 1))) >> 31) & (((NEG_1) << (s)) + 1)))'''
        assert c.count(old)==1
        c=c.replace(old,'''  ((x) - (((((x) >> ((s) - 1)) - 1)) & ((1 << (s)) - 1)))''')
    else:
        c=c.replace('#include "jdhuff.h"','#include <immintrin.h>\n#include "jdhuff.h"',1)
        fast=c.index('LOCAL(boolean)\ndecode_mcu_fast')
        pos=c.rfind('#if defined(__has_feature)',0,fast)
        c=c[:pos]+'''/* Fast reader guarantees bits_left >= n. Packed BEXTR control is
 * start=(bits_left-n), length=n, i.e. bits_left + 255*n. */
#undef PEEK_BITS
#define PEEK_BITS(n) ((int)__bextr_u64(get_buffer, (unsigned int)(bits_left + 255 * (n))))

'''+c[pos:]
    (tree/'src/jdhuff.c').write_text(c)
    delta=''.join(difflib.unified_diff((source/'src/jdhuff.c').read_text().splitlines(True),c.splitlines(True),
                                     fromfile='a/src/jdhuff.c',tofile='b/src/jdhuff.c'))
    (here/(name+'.patch')).write_text(delta)
    # Complete patch for replay against the untouched production checkout.
    complete=''
    for file in ('src/jdhuff.c','src/jdhuff.h','src/jpegint.h'):
        complete+=''.join(difflib.unified_diff((root/file).read_text().splitlines(True),
                                             (tree/file).read_text().splitlines(True),
                                             fromfile='a/'+file,tofile='b/'+file))
    (here/(name+'-complete.patch')).write_text(complete)
    cmake=tree/'CMakeLists.txt'
    cmake.write_text(cmake.read_text()+'\nset_property(SOURCE src/jdhuff.c APPEND PROPERTY COMPILE_OPTIONS '+ ' '.join(flags)+')\n')
    for label,cmd in [('configure',['cmake','-S',tree,'-B',build,'-DCMAKE_BUILD_TYPE=Release',
                                   '-DENABLE_SHARED=OFF','-DBUILD=20261024']),
                      ('build',['cmake','--build',build,'-j','6'])]:
        with (here/f'{name}-{label}.log').open('w') as log:
            subprocess.run(list(map(str,cmd)),stdout=log,stderr=log,check=True)
        commands.append(list(map(str,cmd)))
    isolation[name]={'flags':flags,'archives':{}}
    for lib in ('libjpeg.a','libturbojpeg.a'):
        objdir=build/('matched-'+lib); objdir.mkdir()
        obj=objdir/'jdhuff.c.o'
        extra=[] if lib=='libjpeg.a' else ['-DBMP_SUPPORTED','-DPNG_SUPPORTED','-DSPNG_STATIC','-DPPM_SUPPORTED']
        # Header paths are the same as the control; only the intended source
        # changes and CPU features differ. This source has no __FILE__ strings.
        cmd=['cc','-I'+str(base),'-O3','-DNDEBUG',*extra,*flags,'-c',str(tree/'src/jdhuff.c'),'-o',str(obj)]
        run(cmd); commands.append(cmd)
        shutil.copyfile(base/lib,build/lib); run(['ar','r',build/lib,obj]); run(['ranlib',build/lib])
        members=run(['ar','t',build/lib],text=True).stdout.splitlines()
        assert members==list(original[lib])
        changed=[member for member in members if sha(run(['ar','p',build/lib,member]).stdout)!=original[lib][member]]
        assert changed==['jdhuff.c.o']
        assembly=run(['objdump','-d','--no-show-raw-insn',obj],text=True).stdout
        (here/f'{name}-{lib}.asm').write_text(assembly)
        counts={op:len(re.findall(r'^\s*[0-9a-f]+:\s+'+op+r'\b',assembly,re.M)) for op in
                ('shlx','shrx','sarx','bzhi','bextr','andn','lzcnt','tzcnt','pext','pdep')}
        isolation[name]['archives'][lib]=dict(changed_members=changed,identical_other_members=len(members)-1,
                 archive_sha256=sha((build/lib).read_bytes()),static_instructions=counts)
    with (here/f'{name}-relink.log').open('w') as log:
        subprocess.run(['cmake','--build',str(build),'-j','6'],stdout=log,stderr=log,check=True)
    for lib in ('libjpeg.a','libturbojpeg.a'):
        assert sha((build/lib).read_bytes())==isolation[name]['archives'][lib]['archive_sha256']
    print(name,'built',flush=True)
(here/'isolation.json').write_text(json.dumps(isolation,indent=2)+'\n')
(here/'build-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
