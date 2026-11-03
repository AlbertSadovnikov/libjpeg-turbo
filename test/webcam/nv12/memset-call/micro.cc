#include <cstdio>
#include <cstddef>
#include <cstring>
#include <chrono>
#include <cstdlib>
#include <cstdint>
#include <initializer_list>
#define MJPEG_CLEAR_VARIANT 0
#define mjpeg_clear_experiment clear0
#include "clear.h"
#undef MJPEG_CLEAR_EXPERIMENT_H
#undef MJPEG_CLEAR_VARIANT
#undef mjpeg_clear_experiment
#define MJPEG_CLEAR_VARIANT 1
#define mjpeg_clear_experiment clear1
#include "clear.h"
#undef MJPEG_CLEAR_EXPERIMENT_H
#undef MJPEG_CLEAR_VARIANT
#undef mjpeg_clear_experiment
#define MJPEG_CLEAR_VARIANT 2
#define mjpeg_clear_experiment clear2
#include "clear.h"
#undef MJPEG_CLEAR_EXPERIMENT_H
#undef MJPEG_CLEAR_VARIANT
#undef mjpeg_clear_experiment
#define MJPEG_CLEAR_VARIANT 3
#define mjpeg_clear_experiment clear3
#include "clear.h"
extern "C" void mjpeg_empty_call(void *,size_t);
template<int Kind> __attribute__((noinline)) double measure(void *p) {
  size_t bytes=512;asm volatile("":"+r"(bytes));
  auto once=[&]{
    if constexpr(Kind==0)clear0(p,bytes);
    if constexpr(Kind==1)clear1(p,bytes);
    if constexpr(Kind==2)clear2(p,bytes);
    if constexpr(Kind==3)clear3(p,bytes);
    if constexpr(Kind==4)mjpeg_empty_call(p,bytes);
    asm volatile(""::"r"(p):"memory");
  };
  for(int i=0;i<10000;i++)once();
  uint64_t n=0;auto a=std::chrono::steady_clock::now(),b=a;
  do{for(int i=0;i<16200;i++)once();n+=16200;b=std::chrono::steady_clock::now();}while(std::chrono::duration<double>(b-a).count()<0.15);
  return std::chrono::duration<double,std::nano>(b-a).count()/n;
}
int main(){
  alignas(64) unsigned char area[1536];unsigned checks=0;
  for(int off=0;off<64;off++)for(int blocks=0;blocks<=10;blocks++)for(int k=0;k<4;k++){
    std::memset(area,0xa5,sizeof(area));auto *p=area+64+off;size_t n=blocks*128;
    if(k==0)clear0(p,n);if(k==1)clear1(p,n);if(k==2)clear2(p,n);if(k==3)clear3(p,n);
    for(size_t i=0;i<sizeof(area);i++)if(area[i]!=(i>=size_t(64+off)&&i<size_t(64+off)+n?0:0xa5)){std::fprintf(stderr,"Clear mismatch kind=%d offset=%d blocks=%d byte=%zu\n",k,off,blocks,i);return 1;}
    ++checks;
  }
  std::printf("{\"validation_cases\":%u,\"avx2_available\":%s,\"rounds\":[",checks,__builtin_cpu_supports("avx2")?"true":"false");
  bool comma=false;
  for(int trial=0;trial<5;trial++)for(int off:{32,0,1})for(int j=0;j<6;j++){
    int kind=trial%2?5-j:j;auto *p=area+64+off;double ns=0;
    switch(kind){case 0:ns=measure<0>(p);break;case 1:ns=measure<1>(p);break;case 2:ns=measure<2>(p);break;case 3:ns=measure<3>(p);break;case 4:ns=measure<4>(p);break;case 5:ns=measure<5>(p);break;}
    std::printf("%s{\"trial\":%d,\"offset\":%d,\"kind\":%d,\"ns_per_clear\":%.9f}",comma?",":"",trial,off,kind,ns);comma=true;
  }
  std::puts("]}");
}
