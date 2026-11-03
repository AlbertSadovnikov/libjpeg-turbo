#!/usr/bin/env python3
from pathlib import Path
import sys
here=Path(__file__).resolve().parent;sys.path.insert(0,str(here.parent/'next-round'))
from common import *
old=(TREE/'src/jdhuff.c').read_text();new=old.replace('UINT8 bits, step1, step2, span;','UINT16 control; /* low byte: consumed bits; high byte: total span */\n  UINT8 step1, step2;')
assert new!=old
new=new.replace('e->span = (UINT8)step;','').replace('e->bits = (UINT8)used;','e->control = (UINT16)(used | ((e->step1 + e->step2) << 8));')
new=new.replace('e->span = (UINT8)(e->step1 + step);','')
new=new.replace('const int next_k = k + e.span;\n        if (e.bits && next_k <= DCTSIZE2) {','const unsigned int control = e.control;\n        const unsigned int consumed = control & 255;\n        const int next_k = k + (control >> 8);\n        if (consumed && next_k <= DCTSIZE2) {')
new=new.replace('DROP_BITS(e.bits);','DROP_BITS(consumed);')
patch(here/'control-word.patch',old,new)
for cc in ('clang','gcc'):
 folder=codec_variant(cc,'control-word',new)
 link(cc,'control-word',WORK/'control-wrapper.o',folder)
save(here/'build-summary.json',{'pgo':False,'mtune':False,'entry_bytes':8,'control_word':'consumed bits in low byte, total span in high byte','binaries':{cc:sha(WORK/'bin'/(cc+'-control-word')) for cc in ('clang','gcc')}})
