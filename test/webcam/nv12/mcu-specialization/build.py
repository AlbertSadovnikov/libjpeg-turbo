#!/usr/bin/env python3
"""Fixed four-block MCU expansion versus compact 4:2:2 specialization."""
from pathlib import Path
import difflib
import hashlib
import json
import shutil
import subprocess

here=Path(__file__).resolve().parent;root=here.parents[3]
source=Path('/tmp/mjpeg-stb-src/threshold-pair10');old=(source/'src/jdhuff.c').read_text()
work=Path('/tmp/mjpeg-mcu-specialization');work.mkdir(exist_ok=True)
manifest=json.loads((root/'test/webcam/bmi-intrinsics/pgo-lto/build-summary.json').read_text())
common=Path('/tmp/mjpeg-pgo-lto');google=Path('/tmp/mjpeg-google-bench')
def run(cmd):
    r=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
    if r.returncode:print(r.stderr,flush=True)
    r.check_returncode();return r
def raw(cmd):return subprocess.check_output(list(map(str,cmd)))

start=old.index('LOCAL(boolean)\ndecode_mcu_fast(')
loop=old.index('  for (blkn = 0; blkn < cinfo->blocks_in_MCU; blkn++) {',start)
finish=old.index('\n  if (cinfo->unread_marker != 0)',loop)
end=old.index('\n}\n',finish)+3
generic_body=old[loop+len('  for (blkn = 0; blkn < cinfo->blocks_in_MCU; blkn++) {\n'):finish]
assert generic_body.endswith('  }\n');generic_body=generic_body[:-4]
ac_start=generic_body.index('      for (k = 1; k < DCTSIZE2; k++) {')
ac_end=generic_body.index('\n    } else {',ac_start)
ac_loop=generic_body[ac_start:ac_end]
dc='''    HUFF_DECODE_FAST(s, l, dctbl);
    if (s) {
      FILL_BIT_BUFFER_FAST
      r = GET_BITS(s);
      s = HUFF_EXTEND(r, s);
    }
    s += state.last_dc_val[PREDICTOR];
    state.last_dc_val[PREDICTOR] = s;
    (*block)[0] = (JCOEF)s;
'''
def block(index,predictor,table):
    return '''    JBLOCKROW block = MCU_data[INDEX];
    d_derived_tbl *dctbl = entropy->dc_cur_tbls[TABLE];
    d_derived_tbl *actbl = entropy->ac_cur_tbls[TABLE];
    const multi_entry *fused = entropy->fused_ac_cur_tbls[TABLE];
    register int s, k, r, l;
'''.replace('INDEX',index).replace('TABLE',table)+dc.replace('PREDICTOR',predictor)+ac_loop+'\n'

guard='''  /* This layout/need check runs once per scan, not per block. */
  entropy->fast_422 =
    cinfo->raw_data_out && cinfo->data_precision == 8 &&
    cinfo->jpeg_color_space == JCS_YCbCr && cinfo->num_components == 3 &&
    cinfo->comps_in_scan == 3 && cinfo->blocks_in_MCU == 4 &&
    cinfo->cur_comp_info[0] == &cinfo->comp_info[0] &&
    cinfo->cur_comp_info[1] == &cinfo->comp_info[1] &&
    cinfo->cur_comp_info[2] == &cinfo->comp_info[2] &&
    cinfo->comp_info[0].h_samp_factor == 2 && cinfo->comp_info[0].v_samp_factor == 1 &&
    cinfo->comp_info[1].h_samp_factor == 1 && cinfo->comp_info[1].v_samp_factor == 1 &&
    cinfo->comp_info[2].h_samp_factor == 1 && cinfo->comp_info[2].v_samp_factor == 1 &&
    cinfo->comp_info[0].DCT_scaled_size == 8 &&
    cinfo->comp_info[1].DCT_scaled_size == 8 && cinfo->comp_info[2].DCT_scaled_size == 8 &&
    cinfo->MCU_membership[0] == 0 && cinfo->MCU_membership[1] == 0 &&
    cinfo->MCU_membership[2] == 1 && cinfo->MCU_membership[3] == 2 &&
    entropy->dc_needed[0] && entropy->dc_needed[1] &&
    entropy->dc_needed[2] && entropy->dc_needed[3] &&
    entropy->ac_needed[0] && entropy->ac_needed[1] &&
    entropy->ac_needed[2] && entropy->ac_needed[3];

'''

config={};isolation={}
for compiler in ('gcc','clang'):
    control=manifest['builds'][compiler+'-base'];base=Path(control['build']);config[compiler+'-base']=control
    for kind in ('unroll4','special4','special-loop'):
        name=compiler+'-'+kind;tree=work/(name+'-source');build=work/name
        if tree.exists() or build.exists():raise FileExistsError(name)
        shutil.copytree(source,tree);build.mkdir()
        head=old[start:loop].replace('decode_mcu_fast(', 'decode_mcu_fast_422(',1)
        if kind=='special-loop':
            expanded='''  for (blkn = 0; blkn < 4; blkn++) {
    const int predictor = blkn < 2 ? 0 : blkn - 1;
    const int table_index = blkn == 1 ? 0 : blkn;
'''+block('blkn','predictor','table_index')+'  }\n'
        else:
            head=head.replace('  int blkn;\n','')
            expanded=''
            for i in range(4):
                if kind=='unroll4':body=generic_body.replace('[blkn]','['+str(i)+']')
                else:body=block(str(i),str(0 if i<2 else i-1),str(0 if i<2 else i))
                expanded+='  {\n'+body+'  }\n'
        function=head+expanded+old[finish:end]
        text=old[:end]+'\n\n'+function+old[end:]
        marker='  boolean ac_needed[D_MAX_BLOCKS_IN_MCU];';assert text.count(marker)==1
        text=text.replace(marker,marker+'\n  boolean fast_422;')
        marker='  /* Initialize bitread state variables */';assert text.count(marker)==1
        text=text.replace(marker,guard+marker)
        original_dispatch='      if (!decode_mcu_fast(cinfo, MCU_data)) goto use_slow;';assert text.count(original_dispatch)==1
        text=text.replace(original_dispatch,'''      if (entropy->fast_422 && MCU_data && MCU_data[0] && MCU_data[1] &&
          MCU_data[2] && MCU_data[3]) {
        if (!decode_mcu_fast_422(cinfo, MCU_data)) goto use_slow;
      } else {
        if (!decode_mcu_fast(cinfo, MCU_data)) goto use_slow;
      }''')
        (tree/'src/jdhuff.c').write_text(text)
        (here/(name+'.patch')).write_text(''.join(difflib.unified_diff(old.splitlines(True),text.splitlines(True),fromfile='a/src/jdhuff.c',tofile='b/src/jdhuff.c')))
        record={}
        for lib in ('libjpeg.a','libturbojpeg.a'):
            objdir=build/(lib+'-objects');objdir.mkdir();obj=objdir/'jdhuff.c.o'
            extra=[] if lib=='libjpeg.a' else ['-DBMP_SUPPORTED','-DPNG_SUPPORTED','-DSPNG_STATIC','-DPPM_SUPPORTED']
            run([compiler,*control['flags'],'-mbmi2','-I'+str(base),*extra,'-c',tree/'src/jdhuff.c','-o',obj])
            shutil.copyfile(base/lib,build/lib);run(['ar','r',build/lib,obj]);run(['ranlib',build/lib])
            members=run(['ar','t',base/lib]).stdout.splitlines()
            changed=[m for m in members if raw(['ar','p',base/lib,m])!=raw(['ar','p',build/lib,m])]
            assert changed==['jdhuff.c.o'],changed
            record[lib]=dict(changed_members=changed,sha256=hashlib.sha256((build/lib).read_bytes()).hexdigest())
        binary=build/'nv12-sequence'
        run(['g++' if compiler=='gcc' else 'clang++','-fuse-ld=gold',*control['flags'],common/'sequence.o',common/'heldout-frame.o',
             google/'_deps/googlebenchmark-build/src/libbenchmark.a',build/'libjpeg.a',build/'libturbojpeg.a','-lm','-lpthread','-lrt','-o',binary])
        config[name]=dict(source=str(tree),build=str(build),flags=control['flags'],sequence_binary=str(binary))
        isolation[name]=record
        (here/'experiment.json').write_text(json.dumps(config,indent=2)+'\n');(here/'isolation.json').write_text(json.dumps(isolation,indent=2)+'\n')
        print(name,'built',flush=True)
