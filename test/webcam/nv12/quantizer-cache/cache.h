// Cache the actual signed IFAST multipliers, not JPEG table identities.
#ifndef MJPEG_Y_QUANT_CACHE_H
#define MJPEG_Y_QUANT_CACHE_H
#include <cstdint>
#include <cstring>
#include <immintrin.h>
struct alignas(32) YQuantCache {
  int16_t snapshot[64]{};
  alignas(32) int16_t expanded[128]{};
  bool ready=false;
  bool Update(const void *multipliers) {
    if(ready && std::memcmp(snapshot,multipliers,sizeof(snapshot))==0)return false;
    std::memcpy(snapshot,multipliers,sizeof(snapshot));
    for(int row=0;row<8;row++) {
      auto q=_mm_loadu_si128((const __m128i *)(snapshot+row*8));
      _mm256_store_si256((__m256i *)(expanded+row*16),_mm256_broadcastsi128_si256(q));
    }
    ready=true;
    return true;
  }
};
#endif
