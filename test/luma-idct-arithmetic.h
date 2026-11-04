#pragma once
#include "luma-idct-arithmetic-tables.h"
// Arithmetic experiments. Positive Q15 multiplies round to nearest; shifts
// truncate toward negative infinity. Compensation is applied at table setup.
struct ArithmeticSSE {
  using V=__m128i;
  static inline V add(V a,V b){return _mm_add_epi16(a,b);}
  static inline V sub(V a,V b){return _mm_sub_epi16(a,b);}
  static inline V frac(V a,int c){return _mm_mulhrs_epi16(a,_mm_set1_epi16(c));}
  template<int N> static inline V shift(V a){return _mm_srai_epi16(a,N);}
};
struct ArithmeticAVX {
  using V=__m256i;
  static inline V add(V a,V b){return _mm256_add_epi16(a,b);}
  static inline V sub(V a,V b){return _mm256_sub_epi16(a,b);}
  static inline V frac(V a,int c){return _mm256_mulhrs_epi16(a,_mm256_set1_epi16(c));}
  template<int N> static inline V shift(V a){return _mm256_srai_epi16(a,N);}
};
struct ArithmeticWide {
  using V=long long;
  static inline V add(V a,V b){return a+b;}
  static inline V sub(V a,V b){return a-b;}
  static inline V frac(V a,int c){return (a*c+16384)>>15;}
  template<int N> static inline V shift(V a){return a>>N;}
};
template<int Mode,class O> static inline typename O::V arithmetic_root(typename O::V a){
  if constexpr(Mode==1 || Mode==4)return O::add(a,O::template shift<1>(a));
  if constexpr(Mode==2)return O::sub(O::sub(O::add(a,O::template shift<1>(a)),O::template shift<4>(a)),O::template shift<5>(a));
  if constexpr(Mode==6)return O::sub(O::sub(O::add(a,O::template shift<1>(a)),O::template shift<4>(a)),O::template shift<6>(a));
  if constexpr(Mode==7)return O::sub(O::sub(O::sub(O::add(a,O::template shift<1>(a)),O::template shift<4>(a)),O::template shift<6>(a)),O::template shift<7>(a));
  return O::add(a,O::frac(a,13573));
}
template<class O> static inline typename O::V arithmetic_sine(typename O::V a){
  return O::sub(O::template shift<1>(a),O::template shift<3>(a));
}
template<int Mode,class O> static inline void arithmetic_transform(typename O::V *x){
  using V=typename O::V;
  V p=O::add(x[0],x[4]),q=O::sub(x[0],x[4]);
  V r=O::add(x[2],x[6]),t=O::sub(arithmetic_root<Mode,O>(O::sub(x[2],x[6])),r);
  V e0=O::add(p,r),e3=O::sub(p,r),e1=O::add(q,t),e2=O::sub(q,t);
  V a=O::add(x[5],x[3]),b=O::sub(x[5],x[3]);
  V c=O::add(x[1],x[7]),d=O::sub(x[1],x[7]);
  V o7=O::add(c,a),u=arithmetic_root<Mode,O>(O::sub(c,a));
  V v,w;
  if constexpr(Mode==3 || Mode==4){
    v=O::sub(d,arithmetic_sine<O>(b));w=O::add(b,arithmetic_sine<O>(d));
  }else{
    v=O::sub(O::frac(d,30274),O::frac(b,12540));
    w=O::add(O::frac(b,30274),O::frac(d,12540));
  }
  V o6=O::sub(O::add(v,v),o7),o5=O::sub(u,o6),o4=O::sub(O::add(w,w),o5);
  x[0]=O::add(e0,o7);x[7]=O::sub(e0,o7);x[1]=O::add(e1,o6);x[6]=O::sub(e1,o6);
  x[2]=O::add(e2,o5);x[5]=O::sub(e2,o5);x[3]=O::add(e3,o4);x[4]=O::sub(e3,o4);
}
template<int Mode> __attribute__((noinline)) static void arithmetic_single(const Block *b,const short *q,unsigned char *out){
  __m128i x[8];for(int r=0;r<8;r++)x[r]=_mm_mullo_epi16(_mm_loadu_si128((const __m128i*)(b->data()+8*r)),_mm_loadu_si128((const __m128i*)(q+8*r)));
  arithmetic_transform<Mode,ArithmeticSSE>(x);rotation_transpose16(x);
  arithmetic_transform<Mode,ArithmeticSSE>(x);rotation_transpose16(x);
  for(int r=0;r<8;r++){
    __m128i y=_mm_srai_epi16(_mm_add_epi16(x[r],_mm_set1_epi16(1<<(INTEGER_PASS_BITS+2))),INTEGER_PASS_BITS+3);
    y=_mm_add_epi8(_mm_packs_epi16(y,y),_mm_set1_epi8(-128));
    _mm_storel_epi64((__m128i*)(out+8*r),y);
  }
}
template<int Mode> __attribute__((noinline)) static void arithmetic_pair(const Block *b,const short *q,unsigned char *out){
  __m256i x[8];for(int r=0;r<8;r++){
    __m256i a=_mm256_inserti128_si256(_mm256_castsi128_si256(_mm_loadu_si128((const __m128i*)(b[0].data()+8*r))),_mm_loadu_si128((const __m128i*)(b[1].data()+8*r)),1);
    x[r]=_mm256_mullo_epi16(a,_mm256_broadcastsi128_si256(_mm_loadu_si128((const __m128i*)(q+8*r))));
  }
  arithmetic_transform<Mode,ArithmeticAVX>(x);rotation_transpose162(x);
  arithmetic_transform<Mode,ArithmeticAVX>(x);rotation_transpose162(x);
  for(int r=0;r<8;r++){
    __m256i y=_mm256_srai_epi16(_mm256_add_epi16(x[r],_mm256_set1_epi16(1<<(INTEGER_PASS_BITS+2))),INTEGER_PASS_BITS+3);
    y=_mm256_add_epi8(_mm256_packs_epi16(y,y),_mm256_set1_epi8(-128));
    _mm_storel_epi64((__m128i*)(out+8*r),_mm256_castsi256_si128(y));
    _mm_storel_epi64((__m128i*)(out+64+8*r),_mm256_extracti128_si256(y,1));
  }
}
template<int Mode> __attribute__((noinline)) static void arithmetic_wide(const Block *b,const short *q,unsigned char *out){
  long long x[64];for(int k=0;k<64;k++)x[k]=static_cast<long long>(b->at(k))*q[k];
  for(int pass=0;pass<2;pass++)for(int j=0;j<8;j++){
    long long a[8];for(int k=0;k<8;k++)a[k]=x[pass?j*8+k:k*8+j];
    arithmetic_transform<Mode,ArithmeticWide>(a);
    for(int k=0;k<8;k++)x[pass?j*8+k:k*8+j]=a[k];
  }
  for(int k=0;k<64;k++)out[k]=std::clamp<long long>(((x[k]+(1<<(INTEGER_PASS_BITS+2)))>>(INTEGER_PASS_BITS+3))+128,0,255);
}
struct ArithmeticGuard {
  alignas(32) short weighted_quant[64];
  bool usable=true;
  ArithmeticGuard(const short *q,int mode){
    for(int k=0;k<64;k++){
      int v=int(q[k])*arithmetic_weights[mode][k];
      if(q[k]<0 || v>32767)usable=false;
      weighted_quant[k]=short(std::clamp(v,0,32767));
    }
  }
};
template<int Mode> static inline bool arithmetic_admit(const Block *b,const ArithmeticGuard &g){
  if(!g.usable)return false;
  rotation_J sums=_mm256_setzero_si256(),negative=sums;
  for(int k=0;k<64;k+=16){
    rotation_J a=_mm256_abs_epi16(_mm256_loadu_si256((const rotation_J*)(b->data()+k)));
    negative=_mm256_or_si256(negative,a);
    rotation_J p=_mm256_madd_epi16(a,_mm256_load_si256((const rotation_J*)(g.weighted_quant+k)));
    // Clamp partial sums before adding so even enormous inputs cannot wrap.
    rotation_J packed=_mm256_packus_epi32(p,_mm256_setzero_si256());
    sums=_mm256_adds_epu16(sums,packed);
  }
  if(_mm256_movemask_epi8(_mm256_cmpgt_epi16(_mm256_setzero_si256(),negative)))return false;
  sums=_mm256_min_epu16(sums,_mm256_set1_epi16(32767));
  sums=_mm256_madd_epi16(sums,_mm256_set1_epi16(1));
  rotation_I t=_mm_add_epi32(_mm256_castsi256_si128(sums),_mm256_extracti128_si256(sums,1));
  t=_mm_hadd_epi32(t,t);t=_mm_hadd_epi32(t,t);
  // Generated error budget plus final rounding bias.  Symmetric limit is 32767.
  constexpr int limit=32767-arithmetic_errors[Mode]-(1<<(INTEGER_PASS_BITS+2));
  return _mm_cvtsi128_si32(t)<=limit;
}
template<int Mode> __attribute__((noinline)) static void arithmetic_safe2(const Block *b,const short *q,const ArithmeticGuard &g,unsigned char *out){
  bool a=arithmetic_admit<Mode>(b,g),c=arithmetic_admit<Mode>(b+1,g);
  if(a&&c){arithmetic_pair<Mode>(b,q,out);return;}
  if(a)arithmetic_single<Mode>(b,q,out);else arithmetic_wide<Mode>(b,q,out);
  if(c)arithmetic_single<Mode>(b+1,q,out+64);else arithmetic_wide<Mode>(b+1,q,out+64);
}
