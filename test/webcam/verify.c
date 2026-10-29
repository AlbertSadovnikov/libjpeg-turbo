/* Hash decoded pixels while reusing one decompressor across a mixed sequence.
 * This exercises persistent-cache reuse and invalidation.  Pixel-by-pixel
 * comparisons against djpeg are performed separately by the experiment runner.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include "jpeglib.h"

int main(int argc, char **argv)
{
  if (argc < 3) return 2;
  const char *mode = argv[1];
  struct jpeg_decompress_struct c;
  struct jpeg_error_mgr err;
  c.err = jpeg_std_error(&err);
  jpeg_create_decompress(&c);
  unsigned char *pixels = NULL;
  JSAMPROW *rows = NULL;
  for (int i = 2; i < argc; i++) {
    FILE *file = fopen(argv[i], "rb");
    if (!file || fseek(file, 0, SEEK_END)) return 3;
    long size = ftell(file);
    if (size <= 0 || fseek(file, 0, SEEK_SET)) return 4;
    unsigned char *data = malloc(size);
    if (!data || fread(data, 1, size, file) != (size_t)size) return 5;
    fclose(file);
    jpeg_mem_src(&c, data, size);
    if (jpeg_read_header(&c, TRUE) != JPEG_HEADER_OK || c.data_precision != 8)
      return 6;
    c.out_color_space = !strcmp(mode, "gray") ? JCS_GRAYSCALE : JCS_EXT_BGR;
    c.do_fancy_upsampling = strcmp(mode, "fast-upsample") != 0;
    c.dct_method = !strcmp(mode, "fast-idct") ? JDCT_IFAST : JDCT_ISLOW;
    c.scale_num = 1;
    c.scale_denom = !strcmp(mode, "half") ? 2 : 1;
    if (!jpeg_start_decompress(&c)) return 7;
    size_t stride = (size_t)c.output_width * c.output_components;
    size_t bytes = stride * c.output_height;
    pixels = realloc(pixels, bytes);
    rows = realloc(rows, sizeof(*rows) * c.output_height);
    if (!pixels || !rows) return 8;
    for (JDIMENSION y = 0; y < c.output_height; y++) rows[y] = pixels + y*stride;
    while (c.output_scanline < c.output_height)
      if (!jpeg_read_scanlines(&c, rows + c.output_scanline,
                               c.output_height - c.output_scanline)) return 9;
    unsigned int width = c.output_width, height = c.output_height;
    if (!jpeg_finish_decompress(&c) || c.err->num_warnings) return 10;
    uint64_t hash = UINT64_C(14695981039346656037);
    for (size_t j = 0; j < bytes; j++) {
      hash ^= pixels[j];
      hash *= UINT64_C(1099511628211);
    }
    printf("%d,%u,%u,%zu,%016llx\n", i-2, width, height, bytes,
           (unsigned long long)hash);
    free(data);
  }
  jpeg_destroy_decompress(&c);
  free(rows); free(pixels);
  return 0;
}
