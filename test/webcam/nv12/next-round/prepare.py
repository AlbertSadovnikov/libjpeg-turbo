#!/usr/bin/env python3
from common import *
# Capture a self-contained source reconstruction recipe without borrowing any
# old profiled archive or generated wrapper. Verified no-PGO archive reuse is
# intentional; a full rebuild can use no-mtune/build.py with this source tree.
obj=wrapper('control-wrapper')
for cc in ('clang','gcc'):link(cc,'control',obj)
save(HERE/'baseline.json',{'pgo':False,'mtune':False,'source_tree':str(TREE),'source_patch':str(HERE.parent/'lto-only/codec.patch'),'source_sha256':{str(p.relative_to(TREE)):sha(p) for p in (TREE/'src').glob('*') if p.is_file() and p.suffix in ('.c','.h')},'wrapper_sha256':sha(WORK/'control-wrapper.cc'),'archive_origin':'verified complete no-mtune no-PGO builds','binaries':{cc:sha(WORK/'bin'/(cc+'-control')) for cc in ('clang','gcc')}})
print('Reconstructed prototype source/wrapper from repository patches; verified no-PGO baseline archives.')
