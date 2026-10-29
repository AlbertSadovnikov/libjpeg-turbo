/* The private Huffman header contains C-only register declarations. */
#define JPEG_INTERNALS
#include "jinclude.h"
#include "jpeglib.h"
#include "jdhuff.h"
#include "huffman_tables.h"

struct mjpeg_bench_huffman_tables {
  d_derived_tbl *dc[NUM_HUFF_TBLS];
  d_derived_tbl *ac[NUM_HUFF_TBLS];
};

void mjpeg_bench_rebuild_huffman_tables(
  j_decompress_ptr cinfo, struct mjpeg_bench_huffman_tables *tables)
{
  int i;
  for (i = 0; i < NUM_HUFF_TBLS; i++) {
    if (cinfo->dc_huff_tbl_ptrs[i])
      jpeg_make_d_derived_tbl(cinfo, TRUE, i, &tables->dc[i]);
    if (cinfo->ac_huff_tbl_ptrs[i])
      jpeg_make_d_derived_tbl(cinfo, FALSE, i, &tables->ac[i]);
  }
}

struct mjpeg_bench_huffman_tables *
mjpeg_bench_create_huffman_tables(j_decompress_ptr cinfo)
{
  struct mjpeg_bench_huffman_tables *tables =
    (struct mjpeg_bench_huffman_tables *)(*cinfo->mem->alloc_small)
      ((j_common_ptr)cinfo, JPOOL_IMAGE, sizeof(*tables));
  memset(tables, 0, sizeof(*tables));
  mjpeg_bench_rebuild_huffman_tables(cinfo, tables);
  return tables;
}
