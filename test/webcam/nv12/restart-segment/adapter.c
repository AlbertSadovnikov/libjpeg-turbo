#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#define JPEG_INTERNALS
#include "jpeglib.h"
extern int mjpeg_segment_enabled;
extern int mjpeg_segment_install(j_decompress_ptr);
extern int __real_mjpeg_fusion_begin(j_decompress_ptr, unsigned char *, int, int);
__attribute__((constructor)) static void segment_configure(void)
{
  const char *flag = getenv("MJPEG_SEGMENT");
  mjpeg_segment_enabled = !(flag && flag[0] == '0' && flag[1] == 0);
}
int __wrap_mjpeg_fusion_begin(j_decompress_ptr c, unsigned char *uv,
                            int pitch, int mode)
{
  int fused = __real_mjpeg_fusion_begin(c, uv, pitch, mode);
  if (fused && mode == 3 && c->restart_interval)
    mjpeg_segment_install(c);
  return fused;
}
