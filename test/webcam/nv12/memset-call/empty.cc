// A real opaque call with no writes, to put the call-boundary scale in context.
#include <cstddef>
extern "C" __attribute__((noinline)) void mjpeg_empty_call(void *p,size_t n) {
  asm volatile(""::"r"(p),"r"(n):"memory");
}
