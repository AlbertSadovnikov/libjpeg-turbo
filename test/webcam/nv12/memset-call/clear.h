// Isolated 512-byte MCU clearing experiments; all other sizes retain jzero_far.
#ifndef MJPEG_CLEAR_EXPERIMENT_H
#define MJPEG_CLEAR_EXPERIMENT_H
#ifndef MJPEG_CLEAR_VARIANT
// Preferred candidate by user choice; explicit values retain benchmark controls.
#define MJPEG_CLEAR_VARIANT 3
#endif
#include <stddef.h>
#include <string.h>
#ifdef __cplusplus
extern "C" void jzero_far(void *,size_t);
#endif
static __inline__ __attribute__((always_inline))
void mjpeg_clear_experiment(void *p,size_t bytes) {
#if MJPEG_CLEAR_VARIANT == 1
  // Remove jzero_far's tail jump but retain the dynamic-size libc operation.
  memset(p,0,bytes);
#elif MJPEG_CLEAR_VARIANT == 2
  if(bytes==512) __builtin_memset_inline(p,0,512);
  else jzero_far(p,bytes);
#elif MJPEG_CLEAR_VARIANT == 3 && defined(__x86_64__)
  if(bytes==512 && __builtin_cpu_supports("avx2")) {
    // Keep the controller's generic target. Runtime ISA check precedes every
    // use; all writes are unaligned-safe and restricted to the original range.
    __asm__ __volatile__(
      "vpxor %%ymm0,%%ymm0,%%ymm0\n\t"
      "vmovdqu %%ymm0,0(%0)\n\t"
      "vmovdqu %%ymm0,32(%0)\n\t"
      "vmovdqu %%ymm0,64(%0)\n\t"
      "vmovdqu %%ymm0,96(%0)\n\t"
      "vmovdqu %%ymm0,128(%0)\n\t"
      "vmovdqu %%ymm0,160(%0)\n\t"
      "vmovdqu %%ymm0,192(%0)\n\t"
      "vmovdqu %%ymm0,224(%0)\n\t"
      "vmovdqu %%ymm0,256(%0)\n\t"
      "vmovdqu %%ymm0,288(%0)\n\t"
      "vmovdqu %%ymm0,320(%0)\n\t"
      "vmovdqu %%ymm0,352(%0)\n\t"
      "vmovdqu %%ymm0,384(%0)\n\t"
      "vmovdqu %%ymm0,416(%0)\n\t"
      "vmovdqu %%ymm0,448(%0)\n\t"
      "vmovdqu %%ymm0,480(%0)\n\t"
      "vzeroupper\n\t" : : "r"(p) : "ymm0","memory");
  } else jzero_far(p,bytes);
#else
  jzero_far(p,bytes);
#endif
}
#endif
