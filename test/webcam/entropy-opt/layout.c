#define JPEG_INTERNALS
#include "jinclude.h"
#include "jpeglib.h"
#include "jdhuff.h"
#include <stddef.h>

int main(int argc, char **argv)
{
  struct jpeg_decompress_struct c;
  struct jpeg_error_mgr error;
  FILE *file;
  int i, ac;
  if (argc != 2 || !(file = fopen(argv[1], "rb"))) return 2;
  c.err = jpeg_std_error(&error);
  jpeg_create_decompress(&c);
  jpeg_stdio_src(&c, file);
  if (jpeg_read_header(&c, TRUE) != JPEG_HEADER_OK) return 3;
  printf("table_bytes=%zu lookup_bytes=%zu lookup_offset=%zu\n",
         sizeof(d_derived_tbl),sizeof(((d_derived_tbl *)0)->lookup),
         offsetof(d_derived_tbl,lookup));
  for (ac = 0; ac <= 1; ac++) {
    for (i = 0; i < NUM_HUFF_TBLS; i++) {
      d_derived_tbl *table = NULL;
      if (!(ac ? c.ac_huff_tbl_ptrs[i] : c.dc_huff_tbl_ptrs[i])) continue;
      jpeg_make_d_derived_tbl(&c,!ac,i,&table);
      printf("%s%d lookup_mod64=%zu\n", ac ? "AC" : "DC",i,(size_t)table->lookup & 63);
    }
  }
  jpeg_destroy_decompress(&c);
  fclose(file);
  return 0;
}
