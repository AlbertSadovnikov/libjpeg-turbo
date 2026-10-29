#!/usr/bin/env python3
"""Prepare AVX2-only-codegen and two amortized 32-byte scanner experiments."""
import argparse
import difflib
import importlib.util
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCES = Path('/tmp/mjpeg-avx2-reader-src')
spec = importlib.util.spec_from_file_location('entropy_prepare', HERE.parent/'entropy-opt/prepare.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

REFILL = r'''/* Check 32 bytes at a time and reuse the verified FF-free prefix.
 * The MCU dispatcher supplies 32 additional bytes of buffered lookahead.
 * A reservoir refill still consumes six bytes; a word load's last two bytes
 * are discarded, so only the six consumed bytes need to be FF-free.
 */
#if defined(__x86_64__) && defined(__AVX2__)
#define FILL_BIT_BUFFER_FAST \
  if (bits_left <= 16) { \
    if (fast_clean_bytes < 6) { \
      __m256i scan = _mm256_loadu_si256((const __m256i *)buffer); \
      unsigned int mask = (unsigned int)_mm256_movemask_epi8( \
        _mm256_cmpeq_epi8(scan, _mm256_set1_epi8(-1))); \
      fast_clean_bytes = mask ? __builtin_ctz(mask) : 32; \
    } \
    if (fast_clean_bytes >= 6) { \
      bit_buf_type word; \
      memcpy(&word, buffer, sizeof(word)); \
      get_buffer = (get_buffer << 48) | (__builtin_bswap64(word) >> 16); \
      buffer += 6; \
      bits_left += 48; \
      fast_clean_bytes -= 6; \
    } else { \
      GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE \
      fast_clean_bytes = 0; \
    } \
  }
#else
#define FILL_BIT_BUFFER_FAST \
  if (bits_left <= 16) { \
    GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE GET_BYTE \
  }
#endif
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', nargs='+', choices=['avx2-codegen','avx2-32-local','avx2-32-persistent'])
    parser.add_argument('--resume-pristine', action='store_true',
                        help='Reuse an interrupted copy only if both edited files are still pristine')
    args = parser.parse_args()
    for name in args.only or ['avx2-codegen','avx2-32-local','avx2-32-persistent']:
        target = SOURCES/name
        if target.exists():
            if not args.resume_pristine: raise FileExistsError(target)
            for file in ['src/jdhuff.c','CMakeLists.txt']:
                assert (target/file).read_bytes()==(ROOT/file).read_bytes(),file
        else:
            shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('.git','cmake-build-debug','webcam'))
        c = (ROOT/'src/jdhuff.c').read_text()
        if name != 'avx2-codegen':
            c = base.replace_once(c,'#include "jstdhuff.c"','''#include "jstdhuff.c"
#if defined(__x86_64__) && defined(__AVX2__)
#include <immintrin.h>
#endif''')
            c = base.replace_once(c,base.OLD_REFILL,REFILL)
            start = c.index('decode_mcu_fast(j_decompress_ptr')
            before, fast = c[:start], c[start:]
            fast = base.replace_once(fast,'  int blkn;','''  int blkn;
#if defined(__x86_64__) && defined(__AVX2__)
  int fast_clean_bytes;
#endif''')
            initial = 'entropy->fast_clean_bytes' if name.endswith('persistent') else '0'
            fast = base.replace_once(fast,'  buffer = (JOCTET *)br_state.next_input_byte;',
                '  buffer = (JOCTET *)br_state.next_input_byte;\n'
                '#if defined(__x86_64__) && defined(__AVX2__)\n'
                '  fast_clean_bytes = '+initial+';\n#endif')
            if name.endswith('persistent'):
                fast = base.replace_once(fast,'  entropy->saved = state;',
                    '''  entropy->saved = state;
#if defined(__x86_64__) && defined(__AVX2__)
  entropy->fast_clean_bytes = fast_clean_bytes;
#endif''')
            c = before + fast
            c = base.replace_once(c,
                '  if (cinfo->src->bytes_in_buffer < BUFSIZE * (size_t)cinfo->blocks_in_MCU ||',
                '''  /* Keep the existing per-MCU budget plus a complete scan window. */
  if (cinfo->src->bytes_in_buffer < BUFSIZE * (size_t)cinfo->blocks_in_MCU
#if defined(__x86_64__) && defined(__AVX2__)
      + 32
#endif
      ||''')
            if name.endswith('persistent'):
                c = base.replace_once(c,'  boolean ac_needed[D_MAX_BLOCKS_IN_MCU];',
                    '''  boolean ac_needed[D_MAX_BLOCKS_IN_MCU];
  /* Verified prefix at the next source byte. Valid across fast calls only. */
  int fast_clean_bytes;''')
                c = base.replace_once(c,'  /* Initialize bitread state variables */\n  entropy->bitstate.bits_left = 0;',
                    '  /* Initialize bitread state variables */\n  entropy->fast_clean_bytes = 0;\n  entropy->bitstate.bits_left = 0;')
                # Every source refill or marker/restart transition uses the slow
                # path. Invalidate before entering it, including suspension.
                c = base.replace_once(c,'  /* If we\'ve run out of data, just leave the MCU set to zeroes.',
                    '''  if (!usefast) entropy->fast_clean_bytes = 0;

  /* If we've run out of data, just leave the MCU set to zeroes.''')
                c = base.replace_once(c,'      if (!decode_mcu_fast(cinfo, MCU_data)) goto use_slow;',
                    '''      if (!decode_mcu_fast(cinfo, MCU_data)) {
        entropy->fast_clean_bytes = 0;
        goto use_slow;
      }''')
        (target/'src/jdhuff.c').write_text(c)
        cmake = (ROOT/'CMakeLists.txt').read_text()
        cmake += '\n# AVX2 experiment: all other codec and benchmark C/C++ files keep their flags.\n'
        cmake += 'set_property(SOURCE src/jdhuff.c APPEND PROPERTY COMPILE_OPTIONS -mavx2)\n'
        (target/'CMakeLists.txt').write_text(cmake)
        patch = ''
        for file,new in [('src/jdhuff.c',c),('CMakeLists.txt',cmake)]:
            patch += ''.join(difflib.unified_diff((ROOT/file).read_text().splitlines(True),
                new.splitlines(True),fromfile='a/'+file,tofile='b/'+file))
        (HERE/(name+'.patch')).write_text(patch)
        print(name,target,flush=True)


if __name__=='__main__': main()
