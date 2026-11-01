#!/usr/bin/env python3
"""Isolate reservoir, refill, and entropy-known DC-only dispatch experiments."""
from pathlib import Path
import difflib
import shutil
import sys

here=Path(__file__).resolve().parent
root=here.parents[2]
base=Path('/tmp/mjpeg-stb-src/threshold-pair10')
def replace(s,old,new):
    assert s.count(old)==1,old[:90]
    return s.replace(old,new)

deferred=r'''#define HUFF_DECODE_FAST(s, nb, htbl) \
  FILL_BIT_BUFFER_FAST; \
  s = htbl->lookup[PEEK_BITS(HUFF_LOOKAHEAD)]; \
  nb = s >> HUFF_LOOKAHEAD; \
  if (nb <= HUFF_LOOKAHEAD) { \
    s &= (1 << HUFF_LOOKAHEAD) - 1; \
    DROP_BITS(nb); \
  } else { \
    unsigned int prefix = PEEK_BITS(16); \
    while (prefix >= htbl->maxcode16[nb]) nb++; \
    if (nb > 16) { DROP_BITS(17); s = 0; } \
    else { \
      s = prefix >> (16 - nb); \
      DROP_BITS(nb); \
      s = htbl->pub->huffval[(int)(s + htbl->valoffset[nb]) & 0xFF]; \
    } \
  }
'''
left_macros=r'''
/* Only the fast MCU loop uses this representation. Permanent state and the
 * slow/suspending reader retain their original right-aligned layout. */
static INLINE int left_get_bits(bit_buf_type *buffer, int n)
{
  int value = (int)(*buffer >> (64 - n));
  *buffer <<= n;
  return value;
}
#undef GET_BITS
#undef PEEK_BITS
#undef DROP_BITS
#define GET_BITS(n) (bits_left -= (n), left_get_bits(&get_buffer, (n)))
#define PEEK_BITS(n) ((int)(get_buffer >> (64 - (n))))
#define DROP_BITS(n) (get_buffer <<= (n), bits_left -= (n))

'''

for name in ('defer-drop','left64','variable-refill','prefix4','dc-dispatch','dc-lite'):
    if '--only' in sys.argv and name not in sys.argv[sys.argv.index('--only')+1:]: continue
    target=Path('/tmp/mjpeg-zen-src')/name
    if target.exists() and '--refresh' not in sys.argv: raise FileExistsError(target)
    if not target.exists(): shutil.copytree(base,target)
    files={f:(base/f).read_text() for f in ('src/jdhuff.c','src/jdhuff.h','src/jpegint.h','src/jdcoefct.c')}
    c,h=files['src/jdhuff.c'],files['src/jdhuff.h']
    if name in ('defer-drop','left64'):
        start=h.index('#define HUFF_DECODE_FAST(')
        end=h.index('/* Out-of-line case',start)
        h=h[:start]+deferred+'\n'+h[end:]
    if name=='left64':
        c=replace(c,'  get_buffer = (get_buffer << 8) | c0; \\\n',
                    '  get_buffer |= (bit_buf_type)c0 << (56 - bits_left); \\\n')
        c=replace(c,'      get_buffer &= ~0xFF; \\\n',
                    '      get_buffer &= ~((bit_buf_type)0xFF << (64 - bits_left)); \\\n')
        c=replace(c,'      get_buffer = (get_buffer << 48) | (__builtin_bswap64(word) >> 16); \\\n',
                    '      get_buffer |= (__builtin_bswap64(word) >> 16) << (16 - bits_left); \\\n')
        # Keep attributes immediately before the fast function's declaration.
        pos=c.index('/*\n * MCU decoding: fast path') if '/*\n * MCU decoding: fast path' in c else c.index('LOCAL(boolean)\ndecode_mcu_fast')
        # Inserting before the previous compiler-attribute block avoids moving attributes.
        attr=c.rfind('#if defined(__has_feature)',0,pos)
        if 'no_sanitize' in c[attr:pos]: pos=attr
        c=c[:pos]+left_macros+c[pos:]
        start=c.index('decode_mcu_fast(j_decompress_ptr')
        before,fast=c[:start],c[start:]
        fast=replace(fast,'  BITREAD_STATE_VARS;',
                     '  bit_buf_type get_buffer;\n  int bits_left;\n  bitread_working_state br_state;')
        fast=replace(fast,'  state = entropy->saved;','''  if (bits_left) get_buffer <<= 64 - bits_left;
  else get_buffer = 0;
  state = entropy->saved;''')
        fast=replace(fast,'  BITREAD_SAVE_STATE(cinfo, entropy->bitstate);','''  if (bits_left) get_buffer >>= 64 - bits_left;
  else get_buffer = 0;
  BITREAD_SAVE_STATE(cinfo, entropy->bitstate);''')
        c=before+fast
    elif name=='variable-refill':
        c=replace(c,'''      get_buffer = (get_buffer << 48) | (__builtin_bswap64(word) >> 16); \\
      buffer += 6; \\
      bits_left += 48; \\''',r'''      unsigned int bytes = (64 - bits_left) / 8; \
      unsigned int bits = bytes * 8; \
      if (bits == 64) get_buffer = __builtin_bswap64(word); \
      else get_buffer = (get_buffer << bits) | (__builtin_bswap64(word) >> (64 - bits)); \
      buffer += bytes; \
      bits_left += bits; \\''')
        c=replace(c,'bits_left += bits; '+chr(92)*2,'bits_left += bits; '+chr(92))
    elif name=='prefix4':
        old='''    } else { \\
      GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE \\
    } \\
  }
#else'''
        new=r'''    } else { \
      unsigned int low = (unsigned int)word; \
      unsigned int inv = ~low; \
      if (!((inv - 0x01010101U) & ~inv & 0x80808080U)) { \
        get_buffer = (get_buffer << 32) | __builtin_bswap32(low); \
        buffer += 4; bits_left += 32; \
      } else { \
        GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE \
      } \
    } \
  }
#else'''
        c=replace(c,old,new)
    elif name in ('dc-dispatch','dc-lite'):
        j=files['src/jpegint.h']
        pos=j.index('struct jpeg_entropy_decoder {')
        end=j.index('\n};',pos)
        j=j[:end]+'''
  unsigned int dc_only_mask;
  boolean dc_only_valid;
'''+j[end:]
        files['src/jpegint.h']=j
        c=replace(c,'  entropy->pub.decode_mcu = decode_mcu;','''  entropy->pub.decode_mcu = decode_mcu;
  entropy->pub.dc_only_valid = FALSE;''')
        start=c.index('decode_mcu_fast(j_decompress_ptr')
        end=c.index('#define BUFSIZE',start)
        before,fast,after=c[:start],c[start:end],c[end:]
        fast=replace(fast,'  int blkn;','  int blkn;\n  unsigned int ac_mask = 0;')
        fast=replace(fast,'          DROP_BITS(e.bits);','          ac_mask |= 1U << blkn;\n          DROP_BITS(e.bits);')
        fast=replace(fast,'          s = HUFF_EXTEND(r, s);','          s = HUFF_EXTEND(r, s);\n          ac_mask |= 1U << blkn;')
        fast=replace(fast,'  entropy->saved = state;','''  entropy->saved = state;
  entropy->pub.dc_only_mask = (~ac_mask) & ((1U << cinfo->blocks_in_MCU) - 1);
  entropy->pub.dc_only_valid = TRUE;''')
        after=replace(after,'  int usefast = 1;','  int usefast = 1;\n  entropy->pub.dc_only_valid = FALSE;')
        if name=='dc-lite':
            fast=replace(fast,'  unsigned int ac_mask = 0;','  unsigned int dc_mask = 0;')
            assert fast.count('          ac_mask |= 1U << blkn;\n')==2
            fast=fast.replace('          ac_mask |= 1U << blkn;\n','')
            fast=replace(fast,'\n    }\n  }\n\n  if (cinfo->unread_marker',
                         '\n    }\n    if (block && entropy->ac_needed[blkn] && k == 1) dc_mask |= 1U << blkn;\n  }\n\n  if (cinfo->unread_marker')
            fast=replace(fast,'  entropy->pub.dc_only_mask = (~ac_mask) & ((1U << cinfo->blocks_in_MCU) - 1);',
                         '  entropy->pub.dc_only_mask = dc_mask;')
        c=before+fast+after
        coef=files['src/jdcoefct.c']
        helper='''
#if BITS_IN_JSAMPLE == 8
/* Restricted exact DC-only shortcut. Larger dequantized values retain the
 * normal SIMD path, including its intermediate wrap/saturate semantics. */
static INLINE boolean zen_dc_only(jpeg_component_info *comp, JCOEFPTR block,
                                  _JSAMPARRAY rows, JDIMENSION column)
{
  int dc, sample, y;
  if (!comp->quant_table) return FALSE;
  dc = (int)block[0] * (int)comp->quant_table->quantval[0];
  if (dc < -4096 || dc > 4095) return FALSE;
  sample = ((dc + 4) >> 3) + 128;
  if (sample < 0) sample = 0;
  if (sample > 255) sample = 255;
  for (y = 0; y < 8; y++) memset(rows[y] + column, sample, 8);
  return TRUE;
}
#endif

'''
        pos=coef.index('/* Forward declarations */')
        coef=coef[:pos]+helper+coef[pos:]
        pos=coef.index('decompress_onepass(j_decompress_ptr cinfo, _JSAMPIMAGE output_buf)')
        before,body=coef[:pos],coef[pos:]
        # This declaration stays in the outer function scope, not per block.
        declaration=body.index('\n  JDIMENSION MCU_col_num;')
        body=body[:declaration]+'\n  unsigned int dc_mask;'+body[declaration:]
        needle='''      /* Only perform the IDCT on blocks that are contained within the desired'''
        body=replace(body,needle,'''      dc_mask = 0;
#if BITS_IN_JSAMPLE == 8
      if (cinfo->data_precision == 8 && cinfo->dct_method == JDCT_ISLOW &&
          !cinfo->progressive_mode && !cinfo->arith_code && cinfo->entropy->dc_only_valid)
        dc_mask = cinfo->entropy->dc_only_mask;
#endif

'''+needle)
        old='''                (*inverse_DCT) (cinfo, compptr,
                                (JCOEFPTR)coef->MCU_buffer[blkn + xindex],
                                output_ptr, output_col);'''
        new='''#if BITS_IN_JSAMPLE == 8
                if (!(compptr->_DCT_scaled_size == 8 &&
                      (dc_mask & (1U << (blkn + xindex))) &&
                      zen_dc_only(compptr, (JCOEFPTR)coef->MCU_buffer[blkn + xindex],
                                  output_ptr, output_col)))
#endif
                  (*inverse_DCT) (cinfo, compptr,
                                  (JCOEFPTR)coef->MCU_buffer[blkn + xindex],
                                  output_ptr, output_col);'''
        body=replace(body,old,new)
        files['src/jdcoefct.c']=before+body
    files['src/jdhuff.c'],files['src/jdhuff.h']=c,h
    patch=''
    for file,text in files.items():
        if (target/file).read_text()!=text: (target/file).write_text(text)
        patch+=''.join(difflib.unified_diff((root/file).read_text().splitlines(True),text.splitlines(True),
                                          fromfile='a/'+file,tofile='b/'+file))
    (here/(name+'.patch')).write_text(patch)
    print(name,target,flush=True)
