/* Replay preloaded JPEG frames through the same libjpeg decompression path.
 * Build with the selected build directory first in the include search path.
 * WITH_PROFILE builds additionally expose the existing internal stage timers.
 */
#define _POSIX_C_SOURCE 200809L
#include "jconfigint.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#define JPEG_INTERNALS
#include "jpeglib.h"

typedef struct { unsigned char *data; unsigned long size; } frame;

static double now_ms(void)
{
  struct timespec t;
  if (clock_gettime(CLOCK_MONOTONIC, &t)) exit(2);
  return t.tv_sec * 1000.0 + t.tv_nsec / 1000000.0;
}

static void fail(const char *message)
{
  fprintf(stderr, "%s\n", message);
  exit(2);
}

int main(int argc, char **argv)
{
  if (argc < 5) fail("usage: benchmark MODE PASSES FRAME.jpg ...");
  const char *mode = argv[1];
  int passes = atoi(argv[2]), count = argc - 3;
  int gray = !strcmp(mode, "gray"), half = !strcmp(mode, "half");
  int fastup = !strcmp(mode, "fast-upsample");
  int fastidct = !strcmp(mode, "fast-idct");
  if (passes < 1 || (!gray && !half && !fastup && !fastidct && strcmp(mode, "bgr")))
    fail("invalid mode or pass count");
  frame *frames = calloc(count, sizeof(*frames));
  if (!frames) fail("allocation failed");
  for (int i = 0; i < count; i++) {
    FILE *f = fopen(argv[i + 3], "rb");
    if (!f) fail("cannot open frame");
    if (fseek(f, 0, SEEK_END)) fail("seek failed");
    long size = ftell(f);
    if (size <= 0 || fseek(f, 0, SEEK_SET)) fail("invalid frame size");
    frames[i].size = (unsigned long)size;
    frames[i].data = malloc(size);
    if (!frames[i].data || fread(frames[i].data, 1, size, f) != (size_t)size)
      fail("cannot read frame");
    fclose(f);
  }
  struct jpeg_decompress_struct c;
  struct jpeg_error_mgr err;
  c.err = jpeg_std_error(&err);
  jpeg_create_decompress(&c);
  unsigned char *pixels = NULL;
  JSAMPROW *rows = NULL;
  unsigned int width = 0, height = 0, components = 0;
  puts("pass,frame,bytes,width,height,total_ms,header_ms,setup_ms,scanlines_ms,finish_ms,entropy_ms,idct_ms,upsample_ms,color_ms,merged_ms");
  /* One complete sequence is decoded for warmup, then PASSES measured passes. */
  for (int pass = -1; pass < passes; pass++) {
    for (int i = 0; i < count; i++) {
      double entropy = 0, idct = 0, up = 0, color = 0, merged = 0;
#ifdef WITH_PROFILE
      double e0 = c.master->entropy_elapsed, d0 = c.master->idct_elapsed;
      double u0 = c.master->upsample_elapsed, co0 = c.master->cconvert_elapsed;
      double m0 = c.master->merged_upsample_elapsed;
#endif
      double t0 = now_ms();
      jpeg_mem_src(&c, frames[i].data, frames[i].size);
      if (jpeg_read_header(&c, TRUE) != JPEG_HEADER_OK) fail("invalid header");
      double t1 = now_ms();
      c.out_color_space = gray ? JCS_GRAYSCALE : JCS_EXT_BGR;
      c.do_fancy_upsampling = !fastup;
      c.dct_method = fastidct ? JDCT_IFAST : JDCT_ISLOW;
      c.scale_num = 1;
      c.scale_denom = half ? 2 : 1;
      if (!jpeg_start_decompress(&c)) fail("unexpected input suspension");
      double t2 = now_ms();
      if (!pixels) {
        width = c.output_width; height = c.output_height;
        components = c.output_components;
        size_t stride = (size_t)width * components;
        pixels = malloc(stride * height);
        rows = malloc(sizeof(*rows) * height);
        if (!pixels || !rows) fail("allocation failed");
        memset(pixels, 0, stride * height);
        for (unsigned int y = 0; y < height; y++) rows[y] = pixels + stride*y;
      }
      if (width != c.output_width || height != c.output_height ||
          components != (unsigned int)c.output_components)
        fail("sequence output geometry changed");
      while (c.output_scanline < c.output_height)
        if (!jpeg_read_scanlines(&c, rows + c.output_scanline,
                                 c.output_height - c.output_scanline))
          fail("unexpected input suspension");
      double t3 = now_ms();
      if (!jpeg_finish_decompress(&c)) fail("unexpected input suspension");
      double t4 = now_ms();
      if (c.err->num_warnings) fail("decoder warning");
#ifdef WITH_PROFILE
      entropy = 1000 * (c.master->entropy_elapsed - e0);
      idct = 1000 * (c.master->idct_elapsed - d0);
      up = 1000 * (c.master->upsample_elapsed - u0);
      color = 1000 * (c.master->cconvert_elapsed - co0);
      merged = 1000 * (c.master->merged_upsample_elapsed - m0);
#endif
      if (pass >= 0)
        printf("%d,%d,%lu,%u,%u,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f\n",
               pass, i, frames[i].size, width, height, t4-t0, t1-t0,
               t2-t1, t3-t2, t4-t3, entropy, idct, up, color, merged);
    }
  }
  jpeg_destroy_decompress(&c);
  free(rows); free(pixels);
  for (int i = 0; i < count; i++) free(frames[i].data);
  free(frames);
  return 0;
}
