#!/usr/bin/env python3
from pathlib import Path
import sys,re
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
W=Path('/tmp/mjpeg-restart-tu');W.mkdir(exist_ok=True);UV=Path('/tmp/mjpeg-paired-fast-chroma');D=Path('/tmp/mjpeg-multi-camera');records={}
for cc in ('clang','gcc'):
 base=BASE/cc/'current' if cc=='clang' else Path('/tmp/mjpeg-gcc-deferred-loads/gcc-deferred')
 original=(TREE/'src/jdhuff.c').read_text() if cc=='clang' else (base/'source/src/jdhuff.c').read_text()
 # Reuse the already validated marker-aborting/retry-cleanup algorithm.
 restart=(Path('/tmp/mjpeg-restart-fast')/cc/'source/src/jdhuff.c').read_text()
 prefix=original[:original.index('/*\n * Initialize for a Huffman-compressed scan.')]
 order=re.search(r'const int jpeg_natural_order\[[^\]]+\]\s*=\s*\{.*?\};',(TREE/'src/jutils.c').read_text(),re.S)[0].replace('jpeg_natural_order','mjpeg_restart_natural_order')
 a=restart.index('#ifdef SLOW_SHIFT_32');b=restart.index('METHODDEF(boolean)\ndecode_mcu(');end=restart.index('\n}\n',b)+3
 native='''/* Separate native restart decoder. Preserve upstream license in prefix.
 * Private layout is generated from the exact source compiled into the host.
 * Copy slow helpers under distinct names: no extra references to the original
 * entropy helpers that could alter their LTO call graph.
 */
#define jpeg_fill_bit_buffer mjpeg_restart_fill_bit_buffer
#define jpeg_huff_decode mjpeg_restart_huff_decode
#define jpeg_natural_order mjpeg_restart_natural_order
'''+prefix+'\n'+order+'\n'+restart[a:end]+'''
_Static_assert(sizeof(multi_entry) == 8, "lookup ABI");
_Static_assert(sizeof(JBLOCK) == 128, "coefficient block ABI");
GLOBAL(void)
mjpeg_restart_select(j_decompress_ptr cinfo)
{
  cinfo->entropy->decode_mcu = decode_mcu;
}
'''
 source=original
 marker='METHODDEF(void)\nstart_pass_huff_decoder('
 decl='METHODDEF(boolean) decode_mcu(j_decompress_ptr, JBLOCKROW *);\nEXTERN(void) mjpeg_restart_select(j_decompress_ptr);\n\n'
 assert source.count(marker)==1;source=source.replace(marker,decl+marker)
 marker='  entropy->restarts_to_go = cinfo->restart_interval;\n}'
 assert source.count(marker)==1
 source=source.replace(marker,'''  entropy->restarts_to_go = cinfo->restart_interval;
  /* Reset for every scan, including DRI changes on persistent decoder reuse. */
  entropy->pub.decode_mcu = decode_mcu;
  if (cinfo->restart_interval)
    mjpeg_restart_select(cinfo);
}''')
 patch(here/(cc+'-scan-hook.patch'),original,source)
 folder=W/cc;folder.mkdir(exist_ok=True);tree=folder/'source';shutil.copytree(TREE/'src',tree/'src',dirs_exist_ok=True);(tree/'src/jdhuff.c').write_text(source);(folder/'restart.c').write_text(native)
 lto='-flto=thin' if cc=='clang' else '-flto';ar='llvm-ar-18' if cc=='clang' else 'gcc-ar';ranlib='llvm-ranlib-18' if cc=='clang' else 'gcc-ranlib'
 flags=['-O3','-DNDEBUG',lto,'-mbmi2','-I'+str(BASE/cc/'current')]
 native_flags=['-O3','-DNDEBUG','-fno-lto','-mbmi2','-I'+str(BASE/cc/'current'),'-I'+str(tree/'src')]
 run([cc,*native_flags,'-c',folder/'restart.c','-o',folder/'restart.o'])
 for lib in ('libjpeg.a','libturbojpeg.a'):
  d=folder/(lib+'-objects');d.mkdir(exist_ok=True);obj=d/'jdhuff.c.o';extra=[] if lib=='libjpeg.a' else ['-DBMP_SUPPORTED','-DPNG_SUPPORTED','-DSPNG_STATIC','-DPPM_SUPPORTED']
  run([cc,*flags,*extra,'-c',tree/'src/jdhuff.c','-o',obj]);shutil.copy2(base/lib,folder/lib);run([ar,'r',folder/lib,obj]);run([ranlib,folder/lib])
  changed=[m for m in run([ar,'t',folder/lib],text=True).stdout.splitlines() if run([ar,'p',folder/lib,m]).stdout!=run([ar,'p',base/lib,m]).stdout];assert changed==['jdhuff.c.o'],changed
 for name,archives,extras in [('tu-control',base,[]),('tu-layout',base,[folder/'restart.o']),('tu-fast',folder,[folder/'restart.o'])]:
  binary=link(cc,name,WORK/'uv-paired-wrapper.o',archives=archives,driver=D/'exact-driver.o',extra=[UV/'fast.o',*extras]);records[cc+'-'+name]={'binary':str(binary),'sha256':sha(binary),'archives':{str(archives/lib):sha(archives/lib) for lib in ('libjpeg.a','libturbojpeg.a')}}
 records[cc+'-sources']={'flags':flags,'native_flags':native_flags,'hook_source_sha256':sha(tree/'src/jdhuff.c'),'native_source_sha256':sha(folder/'restart.c'),'native_object_sha256':sha(folder/'restart.o'),'private_prefix_sha256':hashlib.sha256(prefix.encode()).hexdigest()}
save(here/'build-summary.json',{'pgo':False,'explicit_tune':False,'records':records,'scope':'Original core keeps LTO; new restart TU deliberately native. Control is the old build; layout control links the unused native TU. Only jdhuff.c.o changes in core archives.'})
print('Built native restart units, scan hooks and old/layout/candidate controls.',flush=True)
