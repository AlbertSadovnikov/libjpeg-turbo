"""Shared no-PGO/no-tuning build support for the next isolated experiments."""
from pathlib import Path
import json,subprocess,hashlib,shutil,shlex,difflib
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[3]; WORK=Path('/tmp/mjpeg-next-round');WORK.mkdir(exist_ok=True)
BASE=Path('/tmp/mjpeg-no-mtune'); OLD_COMMON=Path('/tmp/mjpeg-lto-only/common'); GOOGLE=Path('/tmp/mjpeg-google-bench')
CONFIG=json.loads((HERE.parent/'no-mtune/build-summary.json').read_text())
assert CONFIG['pgo'] is False and CONFIG['explicit_mtune'] is False
FRAMES=sorted((ROOT/'test/webcam/20261023T230418Z').glob('frame_*.jpg'));assert len(FRAMES)==120
FIXTURES=sorted(Path('/tmp/mjpeg-lut-pipeline/fixtures').glob('*.jpg'));assert len(FIXTURES)==6

def save(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def run(cmd,**kwargs):
 p=subprocess.run(list(map(str,cmd)),capture_output=True,**kwargs)
 if p.returncode:print(p.stderr.decode() if isinstance(p.stderr,bytes) else p.stderr,flush=True)
 p.check_returncode();return p

def prepare():
 tree=WORK/'reference-source'
 if not tree.exists():
  tree.mkdir()
  for rel in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0'):
   if rel and (ROOT/rel).is_file():
    dst=tree/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rel,dst)
  run(['patch','-p1','-i',HERE.parent/'lto-only/codec.patch'],cwd=tree)
  p=tree/'src/jdcoefct.c';s=p.read_text()
  s=s.replace('/home/al/src/libjpeg-turbo/test/webcam/nv12/',str(HERE.parent)+'/');p.write_text(s)
 for cc in ('clang','gcc'):
  for path,wanted in CONFIG['cases'][cc]['current']['sha256'].items():assert sha(path)==wanted,path
 for path,wanted in CONFIG['native_support_sha256'].items():assert sha(path)==wanted,path
 return tree

TREE=prepare()
INCLUDES=['-I'+str(BASE/'clang/current'),'-I'+str(TREE/'src'),'-I'+str(HERE.parent/'fused-chroma'),'-I'+str(ROOT/'benchmarks')]
WRAPPER=(HERE.parent/'fused-chroma/fusion.cc').read_text()
needle='  idct(c,&c->comp_info[0],*blocks[0],output[0],col*16);\n  idct(c,&c->comp_info[0],*blocks[1],output[0],col*16+8);'
assert WRAPPER.count(needle)==1
WRAPPER=WRAPPER.replace('struct alignas(32) Context','extern "C" void mjpeg_idct_ifast_registers(const void *,const JCOEF *,const JCOEF *,JSAMPARRAY,unsigned);\nstruct alignas(32) Context')
WRAPPER=WRAPPER.replace(needle,'  if(c->dct_method==JDCT_IFAST)mjpeg_idct_ifast_registers(c->comp_info[0].dct_table,*blocks[0],*blocks[1],output[0],col*16);\n  else {\n'+needle+'\n  }')

def wrapper(name,text=WRAPPER,extra=()):
 source=WORK/(name+'.cc');source.write_text(text);obj=WORK/(name+'.o')
 run(['g++','-O3','-DNDEBUG','-std=c++17','-mavx2','-mfma',*INCLUDES,*extra,'-c',source,'-o',obj])
 return obj

def codec_variant(cc,name,text):
 folder=WORK/(cc+'-'+name);folder.mkdir(exist_ok=True)
 tree=folder/'source'
 if not tree.exists():shutil.copytree(TREE/'src',tree/'src')
 source=tree/'src/jdhuff.c';source.write_text(text)
 lto='-flto=thin' if cc=='clang' else '-flto';ar='llvm-ar-18' if cc=='clang' else 'gcc-ar';ranlib='llvm-ranlib-18' if cc=='clang' else 'gcc-ranlib'
 for lib in ('libjpeg.a','libturbojpeg.a'):
  objdir=folder/(lib+'-objects');objdir.mkdir(exist_ok=True);obj=objdir/'jdhuff.c.o'
  extra=[] if lib=='libjpeg.a' else ['-DBMP_SUPPORTED','-DPNG_SUPPORTED','-DSPNG_STATIC','-DPPM_SUPPORTED']
  run([cc,'-O3','-DNDEBUG',lto,'-mbmi2','-I'+str(BASE/cc/'current'),*extra,'-c',source,'-o',obj])
  shutil.copy2(BASE/cc/'current'/lib,folder/lib);run([ar,'r',folder/lib,obj]);run([ranlib,folder/lib])
  members=run([ar,'t',folder/lib],text=True).stdout.splitlines()
  changed=[m for m in members if run([ar,'p',folder/lib,m]).stdout!=run([ar,'p',BASE/cc/'current'/lib,m]).stdout]
  assert changed==['jdhuff.c.o'],changed
 save(folder/'build.json',{'pgo':False,'mtune':False,'flags':['-O3','-DNDEBUG',lto,'-mbmi2'],'changed_members':['jdhuff.c.o'],'source_sha256':sha(source),'sha256':{str(folder/lib):sha(folder/lib) for lib in ('libjpeg.a','libturbojpeg.a')}})
 return folder

def link(cc,name,obj,archives=None,driver=None,extra=()):
 archives=Path(archives) if archives else BASE/cc/'current';driver=Path(driver) if driver else OLD_COMMON/'current-driver.o'
 (WORK/'bin').mkdir(exist_ok=True)
 binary=WORK/'bin'/(cc+'-'+name);lto='-flto=thin' if cc=='clang' else '-flto';cxx='clang++' if cc=='clang' else 'g++'
 run([cxx,'-O3','-DNDEBUG',lto,'-fuse-ld=gold',driver,obj,OLD_COMMON/'registers.o',OLD_COMMON/'exact.o',OLD_COMMON/'frame.o',*extra,GOOGLE/'_deps/googlebenchmark-build/src/libbenchmark.a',archives/'libjpeg.a',archives/'libturbojpeg.a','-lm','-lpthread','-lrt','-o',binary])
 return binary

def execute(binary,*args):
 p=run(['taskset','-c','0',binary,*args],text=True);assert not p.stderr,p.stderr;return json.loads(p.stdout)

def patch(path,old,new):
 Path(path).write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/src/jdhuff.c',tofile='b/src/jdhuff.c')))
