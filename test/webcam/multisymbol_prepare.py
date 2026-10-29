#!/usr/bin/env python3
"""Create isolated scalar-bulk + fused one/two AC symbol experiments."""
from pathlib import Path
import difflib
import shutil
import subprocess

root = Path(__file__).resolve().parents[2]
out = root / 'test/webcam/multisymbol'
out.mkdir(exist_ok=True)
target = Path('/tmp/mjpeg-multisymbol-src')
if target.exists():
    raise FileExistsError(target)
shutil.copytree(root, target, ignore=shutil.ignore_patterns('.git', 'webcam', 'cmake-build-debug'))
for patch in ('entropy-opt/bulk-once.patch', 'fused-ac/fused-ac.patch'):
    subprocess.run(['patch', '-p1', '-i', str(root / 'test/webcam' / patch)], cwd=target, check=True)
file = target / 'src/jdhuff.c'
c = file.read_text()
start = c.index('/* Zero denotes a miss.')
end = c.index('\ntypedef struct {\n  struct jpeg_entropy_decoder', start)
c = c[:start] + r'''
#ifndef MJPEG_PAIR
#define MJPEG_PAIR 1
#endif
/* Exactly eight bytes per entry. Zero bits means fall back. A pair contains
 * only nonzero coefficients: EOB and ZRL never cross a block boundary here.
 */
typedef struct {
  INT16 value1, value2;
  UINT8 bits, step1, step2, count;
} multi_entry;
typedef struct {
  boolean valid;
  UINT8 bits[17], huffval[256];
  multi_entry lookup[1 << MJPEG_FUSED_BITS];
} fused_ac_cache;

/* Decode one complete symbol+amplitude from a fixed-width prefix at build
 * time. Never read past that prefix. Unusual/malformed symbols fall back.
 */
LOCAL(int)
prefix_symbol(JHUFF_TBL *h, unsigned int prefix, int *used,
              int *value, int *step)
{
  unsigned int code = 0;
  int l, p = 0, available = MJPEG_FUSED_BITS - *used;
  for (l = 1; l <= available; l++) {
    unsigned int candidate = (prefix >> (available - l)) & ((1U << l) - 1);
    int count = h->bits[l];
    if (candidate >= code && candidate - code < (unsigned int)count) {
      int symbol = h->huffval[p + candidate - code];
      int n = symbol & 15;
      unsigned int amplitude;
      if (!n || n > 10 || l + n > available) return 0;
      amplitude = (prefix >> (available - l - n)) & ((1U << n) - 1);
      *value = (int)amplitude;
      if (amplitude < (1U << (n - 1))) *value -= (1 << n) - 1;
      *step = (symbol >> 4) + 1;
      *used += l + n;
      return 1;
    }
    p += count;
    code = (code + count) << 1;
  }
  return 0;
}

LOCAL(const multi_entry *)
get_fused_ac_lookup(j_decompress_ptr cinfo, int tblno)
{
  JHUFF_TBL *h = cinfo->ac_huff_tbl_ptrs[tblno];
  fused_ac_cache *cache = (fused_ac_cache *)cinfo->master->fused_ac_cache[tblno];
  unsigned int prefix;
  if (!cache) {
    cache = (fused_ac_cache *)(*cinfo->mem->alloc_small)
      ((j_common_ptr)cinfo, JPOOL_PERMANENT, sizeof(*cache));
    cache->valid = FALSE;
    cinfo->master->fused_ac_cache[tblno] = cache;
  }
  if (cache->valid && !memcmp(cache->bits, h->bits, sizeof(cache->bits)) &&
      !memcmp(cache->huffval, h->huffval, sizeof(cache->huffval)))
    return cache->lookup;
  memset(cache->lookup, 0, sizeof(cache->lookup));
  for (prefix = 0; prefix < (1U << MJPEG_FUSED_BITS); prefix++) {
    int used = 0, value, step;
    multi_entry *e = &cache->lookup[prefix];
    if (!prefix_symbol(h, prefix, &used, &value, &step)) continue;
    e->value1 = (INT16)value;
    e->step1 = (UINT8)step;
    e->count = 1;
    e->bits = (UINT8)used;
    if (MJPEG_PAIR && prefix_symbol(h, prefix, &used, &value, &step)) {
      e->value2 = (INT16)value;
      e->step2 = (UINT8)step;
      e->count = 2;
      e->bits = (UINT8)used;
    }
  }
  memcpy(cache->bits, h->bits, sizeof(cache->bits));
  memcpy(cache->huffval, h->huffval, sizeof(cache->huffval));
  cache->valid = TRUE;
  return cache->lookup;
}
''' + c[end:]
c = c.replace('const unsigned int *fused_ac_cur_tbls', 'const multi_entry *fused_ac_cur_tbls')
start = c.index('      const unsigned int *fused =')
end = c.index('        HUFF_DECODE_FAST(s, l, actbl);', start)
c = c[:start] + r'''      const multi_entry *fused = entropy->fused_ac_cur_tbls[blkn];

      for (k = 1; k < DCTSIZE2; k++) {
        multi_entry e;
        FILL_BIT_BUFFER_FAST
        e = fused[PEEK_BITS(MJPEG_FUSED_BITS)];
        /* Do not speculatively consume a symbol from the next block. */
        if (e.bits && k + e.step1 + e.step2 <= DCTSIZE2) {
          DROP_BITS(e.bits);
          k += e.step1 - 1;
          (*block)[jpeg_natural_order[k]] = e.value1;
          if (e.count == 2) {
            k += e.step2;
            (*block)[jpeg_natural_order[k]] = e.value2;
          }
          continue;
        }
''' + c[end:]
file.write_text(c)
patch = ''
for name in ('src/jdhuff.c', 'src/jpegint.h'):
    patch += ''.join(difflib.unified_diff((root/name).read_text().splitlines(True),
                                        (target/name).read_text().splitlines(True),
                                        fromfile='a/'+name, tofile='b/'+name))
(out/'multisymbol.patch').write_text(patch)
print(target)
