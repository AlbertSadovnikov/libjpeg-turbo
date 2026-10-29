#!/usr/bin/env python3
"""Create isolated decoder variants and reviewable patches from this checkout."""
import difflib
import argparse
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCES = Path('/tmp/mjpeg-entropy-opt-src')

OLD_REFILL = '''/* Pre-fetch 48 bytes, because the holding register is 64-bit */
#define FILL_BIT_BUFFER_FAST \\
  if (bits_left <= 16) { \\
    GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE \\
  }
'''

NEW_REFILL = '''/* Append 48 bits at once when an eight-byte lookahead has no FF.
 * memcpy permits unaligned input without violating aliasing rules.  The
 * explicit bound covers the whole load; markers and stuffing retain the
 * original byte reader.  Examining two extra bytes is conservative.
 */
#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
#define FILL_BIT_BUFFER_FAST \\
  if (bits_left <= 16) { \\
    bit_buf_type word = 0, inverted; \\
    if ((size_t)(fast_end - buffer) >= sizeof(word)) { \\
      memcpy(&word, buffer, sizeof(word)); \\
      inverted = ~word; \\
      if (!((inverted - 0x0101010101010101ULL) & \\
            ~inverted & 0x8080808080808080ULL)) { \\
        get_buffer = (get_buffer << 48) | (__builtin_bswap64(word) >> 16); \\
        buffer += 6; \\
        bits_left += 48; \\
      } else { \\
        GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE \\
      } \\
    } else { \\
      GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE \\
    } \\
  }
#else
#define FILL_BIT_BUFFER_FAST \\
  if (bits_left <= 16) { \\
    GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE \\
  }
#endif
'''

NEW_REFILL_ONCE = '''/* The MCU dispatcher reserves eight extra buffered bytes before using
 * this reader.  This hoists the load-bound check out of each refill.
 */
#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
#define FILL_BIT_BUFFER_FAST \\
  if (bits_left <= 16) { \\
    bit_buf_type word, inverted; \\
    memcpy(&word, buffer, sizeof(word)); \\
    inverted = ~word; \\
    if (!((inverted - 0x0101010101010101ULL) & \\
          ~inverted & 0x8080808080808080ULL)) { \\
      get_buffer = (get_buffer << 48) | (__builtin_bswap64(word) >> 16); \\
      buffer += 6; \\
      bits_left += 48; \\
    } else { \\
      GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE \\
    } \\
  }
#else
#define FILL_BIT_BUFFER_FAST \\
  if (bits_left <= 16) { \\
    GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE \\
  }
#endif
'''

OLD_ALLOC = '''  if (*pdtbl == NULL)
    *pdtbl = (d_derived_tbl *)
      (*cinfo->mem->alloc_small) ((j_common_ptr)cinfo, JPOOL_IMAGE,
                                  sizeof(d_derived_tbl));'''

NEW_ALLOC = '''  if (*pdtbl == NULL) {
    /* Align only the hot lookup, leaving the memory manager and the other
     * structure fields unchanged.  Image-pool ownership permits an interior
     * pointer; no individual object is freed.  Both layouts have an
     * eight-byte-aligned lookup offset on the tested 64-bit target.
     */
    unsigned char *base = (unsigned char *)(*cinfo->mem->alloc_small)
      ((j_common_ptr)cinfo, JPOOL_IMAGE, sizeof(d_derived_tbl) + 63);
    size_t misalignment =
      ((size_t)base + offsetof(d_derived_tbl, lookup)) & 63;
    *pdtbl = (d_derived_tbl *)(base + ((64 - misalignment) & 63));
  }'''


def replace_once(text, old, new):
    assert text.count(old) == 1, old[:100]
    return text.replace(old, new, 1)


def main():
    variants = {
        'bulk': (True, False, False),
        'compact': (False, True, False),
        'aligned': (False, False, True),
        'compact-aligned': (False, True, True),
        'bulk-compact-aligned': (True, True, True),
        'bulk-once': (True, False, False),
        'bulk-sse2': (True, False, False),
    }
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', choices=list(variants), nargs='+')
    args = parser.parse_args()
    for name, (bulk, compact, aligned) in variants.items():
        if args.only and name not in args.only:
            continue
        target = SOURCES/name
        if target.exists():
            raise FileExistsError(target)
        shutil.copytree(ROOT, target,
                        ignore=shutil.ignore_patterns('.git', 'cmake-build-debug', 'webcam'))
        c = (ROOT/'src/jdhuff.c').read_text()
        h = (ROOT/'src/jdhuff.h').read_text()
        if name in ('bulk-once','bulk-sse2'):
            refill = NEW_REFILL_ONCE
            if name == 'bulk-sse2':
                refill = replace_once(refill, 'bit_buf_type word, inverted;', 'bit_buf_type word;')
                start = refill.index('    inverted = ~word;')
                end = refill.index('      get_buffer =', start)
                refill = refill[:start] + '    if (!fast_word_has_ff(word)) { \\\n' + refill[end:]
                c = replace_once(c, '#include "jstdhuff.c"', '''#include "jstdhuff.c"

#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
#include <emmintrin.h>
static INLINE int fast_word_has_ff(bit_buf_type word)
{
  __m128i bytes = _mm_cvtsi64_si128((long long)word);
  return _mm_movemask_epi8(_mm_cmpeq_epi8(bytes, _mm_set1_epi8(-1)));
}
#endif''')
            c = replace_once(c, OLD_REFILL, refill)
            c = replace_once(c,
                '  if (cinfo->src->bytes_in_buffer < BUFSIZE * (size_t)cinfo->blocks_in_MCU ||',
                '''  /* Preserve the byte reader's conservative per-MCU budget, with
   * additional space for the wider lookahead load. */
  if (cinfo->src->bytes_in_buffer < BUFSIZE * (size_t)cinfo->blocks_in_MCU
#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
      + 8
#endif
      ||''')
        elif bulk:
            c = replace_once(c, OLD_REFILL, NEW_REFILL)
            # Only the fast decoder needs the load bound.
            start = c.index('decode_mcu_fast(j_decompress_ptr')
            before, fast = c[:start], c[start:]
            fast = replace_once(fast, '  JOCTET *buffer;', '''  JOCTET *buffer;
#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
  const JOCTET *fast_end;
#endif''')
            fast = replace_once(fast, '  buffer = (JOCTET *)br_state.next_input_byte;',
                                '''  buffer = (JOCTET *)br_state.next_input_byte;
#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
  fast_end = br_state.next_input_byte + br_state.bytes_in_buffer;
#endif''')
            c = before + fast
        if compact:
            h = replace_once(h, '  int lookup[1 << HUFF_LOOKAHEAD];',
                             '''  /* Length/symbol entries fit in 12 bits at 8-bit lookahead. */
  UINT16 lookup[1 << HUFF_LOOKAHEAD];''')
        if aligned:
            c = replace_once(c, OLD_ALLOC, NEW_ALLOC)
        (target/'src/jdhuff.c').write_text(c)
        (target/'src/jdhuff.h').write_text(h)
        patch = ''
        for file, new in [('src/jdhuff.c', c), ('src/jdhuff.h', h)]:
            patch += ''.join(difflib.unified_diff(
                (ROOT/file).read_text().splitlines(True), new.splitlines(True),
                fromfile='a/'+file, tofile='b/'+file))
        (HERE/(name+'.patch')).write_text(patch)
        print(name, target, flush=True)


if __name__ == '__main__':
    main()
