#!/usr/bin/env python3
"""Build isolated variants inspired by stb's compact AC entries and fallback."""
from pathlib import Path
import difflib
import shutil

here=Path(__file__).resolve().parent
root=here.parents[2]
base=Path('/tmp/mjpeg-multisymbol-branchless-src')

def replace(s,old,new):
    assert s.count(old)==1,old[:100]
    return s.replace(old,new)

for name in ('compact9','compact-pair10','threshold-pair10'):
    target=Path('/tmp/mjpeg-stb-src')/name
    if target.exists(): raise FileExistsError(target)
    shutil.copytree(base,target)
    c=(target/'src/jdhuff.c').read_text()
    h=(target/'src/jdhuff.h').read_text()
    if name=='compact9':
        c=c.replace('#define MJPEG_FUSED_BITS  10','#define MJPEG_FUSED_BITS  9')
        c=c.replace('/* Exactly eight bytes per entry. Zero bits means fall back. A pair contains\n * only nonzero coefficients: EOB and ZRL never cross a block boundary here.\n */',
                    '/* Two-byte stb-style entry: signed amplitude8, run4, consumed length4.\n * Zero denotes fallback; EOB and ZRL remain in the ordinary decoder.\n */')
        c=replace(c,'''typedef struct {
  INT16 value1, value2;
  UINT8 bits, step1, step2, count;
} multi_entry;''','typedef UINT16 multi_entry;')
        start=c.index('    e->value1 = e->value2 = (INT16)value;')
        end=c.index('\n  }\n  memcpy(cache->bits',start)
        c=c[:start]+'''    if (value < -128 || value > 127) continue;
    *e = ((unsigned int)(UINT8)value << 8) |
         ((unsigned int)(step - 1) << 4) | (unsigned int)used;'''+c[end:]
        start=c.index('        /* Do not speculatively consume')
        end=c.index('        HUFF_DECODE_FAST(s, l, actbl);',start)
        c=c[:start]+'''        if (e && k + ((e >> 4) & 15) < DCTSIZE2) {
          DROP_BITS(e & 15);
          k += (e >> 4) & 15;
          (*block)[jpeg_natural_order[k]] = (JCOEF)(signed char)(e >> 8);
          continue;
        }
'''+c[end:]
    elif name=='compact-pair10':
        c=c.replace('/* Exactly eight bytes per entry. Zero bits means fall back. A pair contains\n * only nonzero coefficients: EOB and ZRL never cross a block boundary here.\n */',
                    '/* Four-byte entry: value2[31:24], value1[23:16], run2[15:12],\n * run1[11:8], pair flag[4], consumed bits[3:0]. Zero denotes fallback.\n */')
        c=replace(c,'''typedef struct {
  INT16 value1, value2;
  UINT8 bits, step1, step2, count;
} multi_entry;''','typedef unsigned int multi_entry;')
        start=c.index('    e->value1 = e->value2 = (INT16)value;')
        end=c.index('\n  }\n  memcpy(cache->bits',start)
        c=c[:start]+'''    unsigned int first;
    if (value < -128 || value > 127) continue;
    first = (unsigned int)(UINT8)value;
    *e = (first << 24) | (first << 16) |
         ((unsigned int)(step - 1) << 8) | (unsigned int)used;
    if (prefix_symbol(h, prefix, &used, &value, &step) && value >= -128 && value <= 127) {
      *e = (first << 16) | ((unsigned int)(UINT8)value << 24) |
           (*e & 0xf00U) | ((unsigned int)(step - 1) << 12) |
           16U | (unsigned int)used;
    }'''+c[end:]
        start=c.index('        /* Do not speculatively consume')
        end=c.index('        HUFF_DECODE_FAST(s, l, actbl);',start)
        c=c[:start]+'''        unsigned int step1 = ((e >> 8) & 15) + 1;
        unsigned int step2 = ((e >> 12) & 15) + ((e >> 4) & 1);
        if (e && k + step1 + step2 <= DCTSIZE2) {
          DROP_BITS(e & 15);
          k += step1 - 1;
          (*block)[jpeg_natural_order[k]] = (JCOEF)(signed char)(e >> 16);
          k += step2;
          (*block)[jpeg_natural_order[k]] = (JCOEF)(signed char)(e >> 24);
          continue;
        }
'''+c[end:]
    else:
        h=replace(h,'  int lookup[1 << HUFF_LOOKAHEAD];',
                  '  int lookup[1 << HUFF_LOOKAHEAD];\n  unsigned int maxcode16[18];')
        c=replace(c,'  dtbl->valoffset[17] = 0;', '''  for (l = 1; l <= 16; l++)
    dtbl->maxcode16[l] = (unsigned int)(dtbl->maxcode[l] + 1) << (16 - l);
  dtbl->maxcode16[17] = 65536U;
  dtbl->valoffset[17] = 0;''')
        start=h.index('    /* Equivalent of jpeg_huff_decode() */')
        end=h.index('\n  }\n',start)
        h=h[:start]+'''    unsigned int prefix; \\
    bits_left += nb; \\
    prefix = PEEK_BITS(16); \\
    while (prefix >= htbl->maxcode16[nb]) nb++; \\
    if (nb > 16) { \\
      DROP_BITS(17); \\
      s = 0; \\
    } else { \\
      s = prefix >> (16 - nb); \\
      DROP_BITS(nb); \\
      s = htbl->pub->huffval[(int)(s + htbl->valoffset[nb]) & 0xFF]; \\
    } \\'''+h[end:]
    (target/'src/jdhuff.c').write_text(c)
    (target/'src/jdhuff.h').write_text(h)
    patch=''
    for file in ('src/jdhuff.c','src/jdhuff.h','src/jpegint.h'):
        patch+=''.join(difflib.unified_diff((root/file).read_text().splitlines(True),
                                          (target/file).read_text().splitlines(True),
                                          fromfile='a/'+file,tofile='b/'+file))
    (here/(name+'.patch')).write_text(patch)
    print(name,target)
