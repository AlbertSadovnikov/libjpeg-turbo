#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
old=WRAPPER
start=old.index('    for(int j=0;j<6;j++) {');end=old.index('    transpose4(a,b,c,d,f+half*4);',start)
loop=old[start:end];assert loop.endswith('    }\n')
body=loop[loop.index('\n')+1:-6]
replacement='''    // Only skip contributions proved exactly zero in BOTH Cb/Cr halves.
    unsigned long long high=0,word;
    for(int v=5;v<8;v++) {
      std::memcpy(&word,cb+v*8+half*4,8);high|=word;
      std::memcpy(&word,cr+v*8+half*4,8);high|=word;
    }
    for(int j=0;j<3;j++) {
'''+body+'''    }
    if(high)for(int j=3;j<6;j++) {
'''+body+'''    }
'''
new=old[:start]+replacement+old[end:]
(WORK/'zero-wrapper-source.cc').write_text(new)
(here/'wrapper.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='control-wrapper.cc',tofile='zero-wrapper.cc')))
obj=wrapper('zero-wrapper',new)
for cc in ('clang','gcc'):link(cc,'zero-groups',obj)
# Independent reference/candidate TLS contexts for literal direct UV checking.
for name,text in [('ref',old),('zero',new)]:
 symbols=['mjpeg_fusion_begin','mjpeg_fusion_end','mjpeg_fusion_mcu','mjpeg_chroma_reduced_test']
 opts=['-D'+symbol+'='+name+'_'+symbol for symbol in symbols]
 wrapper('zero-check-'+name,text,extra=opts)
save(here/'build-summary.json',{'pgo':False,'mtune':False,'source_sha256':sha(WORK/'zero-wrapper-source.cc'),'checked_groups':'v=5,6,7 combined per horizontal half; both Cb/Cr must be zero','binaries':{cc:sha(WORK/'bin'/(cc+'-zero-groups')) for cc in ('clang','gcc')}})
