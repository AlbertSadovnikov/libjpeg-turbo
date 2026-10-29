#!/usr/bin/env python3
from pathlib import Path
import shutil
import difflib

root = Path(__file__).resolve().parents[3]
source = Path('/tmp/mjpeg-multisymbol-src')
target = Path('/tmp/mjpeg-multisymbol-branchless-src')
shutil.copytree(source, target)
file = target/'src/jdhuff.c'
c = file.read_text()
c = c.replace('    e->value1 = (INT16)value;',
              '    e->value1 = e->value2 = (INT16)value;')
old = '''          if (e.count == 2) {
            k += e.step2;
            (*block)[jpeg_natural_order[k]] = e.value2;
          }'''
new = '''          /* A single-symbol entry has step2=0 and value2=value1.
           * Repeat its store instead of branching on the decoded count. */
          k += e.step2;
          (*block)[jpeg_natural_order[k]] = e.value2;'''
assert c.count(old) == 1
c = c.replace(old, new)
file.write_text(c)
patch = ''
for name in ('src/jdhuff.c', 'src/jpegint.h'):
    patch += ''.join(difflib.unified_diff((root/name).read_text().splitlines(True),
                                        (target/name).read_text().splitlines(True),
                                        fromfile='a/'+name, tofile='b/'+name))
(Path(__file__).resolve().parent/'multisymbol-branchless.patch').write_text(patch)
