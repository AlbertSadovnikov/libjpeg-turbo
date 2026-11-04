#pragma once
// Experimental odd-part rotation: c=cos(pi/8), s=sin(pi/8).
// The odd terms are 2*(c*d-s*b)-o7 and 2*(c*b+s*d)-o5.
// Each product rounds independently in Q15, then the sums are doubled;
// this deliberately differs from the previous kernel's integer rounding.
#ifndef INTEGER_PASS_BITS
#define INTEGER_PASS_BITS 2
#endif
static_assert(INTEGER_PASS_BITS>=2 && INTEGER_PASS_BITS<=4,"supported precision is 2..4");
// Experimental integer approximation of the scaled cosine transform.
// Shares the AAN real-valued factorization with float4, but not IFAST's
// constants, multiply truncation, or prescaling.  All arithmetic wraps at 16
// bits, except rounded fractional multiplies and the final saturating store.
using rotation_I = __m128i;
static inline rotation_I rotation_add(rotation_I a,rotation_I b){return _mm_add_epi16(a,b);}
static inline rotation_I rotation_sub(rotation_I a,rotation_I b){return _mm_sub_epi16(a,b);}
// Fractional multiplies round to nearest, ties toward positive infinity;
// integer additions supply the whole part of sqrt(2)*x, avoiding IFAST's pre-multiply
// left shift (which discards the top two bits). Q15 fractions are derived
// by rounding the real constants, not by rescaling IFAST's 8-bit constants.
static inline rotation_I rotation_frac(rotation_I x,int c){return _mm_mulhrs_epi16(x,_mm_set1_epi16(c));}
static inline rotation_I rotation_root2(rotation_I x){return rotation_add(x,rotation_frac(x,13573));}
static inline void rotation_aan(rotation_I *x){
  rotation_I p=rotation_add(x[0],x[4]),q=rotation_sub(x[0],x[4]);
  rotation_I r=rotation_add(x[2],x[6]),t=rotation_sub(rotation_root2(rotation_sub(x[2],x[6])),r);
  rotation_I e0=rotation_add(p,r),e3=rotation_sub(p,r),e1=rotation_add(q,t),e2=rotation_sub(q,t);
  rotation_I a=rotation_add(x[5],x[3]),b=rotation_sub(x[5],x[3]);
  rotation_I c=rotation_add(x[1],x[7]),d=rotation_sub(x[1],x[7]);
  rotation_I o7=rotation_add(c,a),u=rotation_root2(rotation_sub(c,a));
  rotation_I v=rotation_sub(rotation_frac(d,30274),rotation_frac(b,12540));
  rotation_I w=rotation_add(rotation_frac(b,30274),rotation_frac(d,12540));
  rotation_I o6=rotation_sub(rotation_add(v,v),o7);
  rotation_I o5=rotation_sub(u,o6),o4=rotation_sub(rotation_add(w,w),o5);
  x[0]=rotation_add(e0,o7);x[7]=rotation_sub(e0,o7);x[1]=rotation_add(e1,o6);x[6]=rotation_sub(e1,o6);
  x[2]=rotation_add(e2,o5);x[5]=rotation_sub(e2,o5);x[3]=rotation_add(e3,o4);x[4]=rotation_sub(e3,o4);
}
static inline void rotation_transpose16(rotation_I *x){
  rotation_I a[8],b[8];
  for(int i=0;i<4;i++){a[2*i]=_mm_unpacklo_epi16(x[2*i],x[2*i+1]);a[2*i+1]=_mm_unpackhi_epi16(x[2*i],x[2*i+1]);}
  for(int i=0;i<2;i++)for(int j=0;j<2;j++){
    b[4*i+j*2]=_mm_unpacklo_epi32(a[4*i+j],a[4*i+j+2]);
    b[4*i+j*2+1]=_mm_unpackhi_epi32(a[4*i+j],a[4*i+j+2]);
  }
  for(int i=0;i<4;i++){x[2*i]=_mm_unpacklo_epi64(b[i],b[i+4]);x[2*i+1]=_mm_unpackhi_epi64(b[i],b[i+4]);}
}
__attribute__((noinline)) static void rotation_candidate(const Block *b,const short *q,unsigned char *out){
  rotation_I x[8];for(int r=0;r<8;r++)x[r]=_mm_mullo_epi16(_mm_loadu_si128((const rotation_I*)(b->data()+8*r)),_mm_loadu_si128((const rotation_I*)(q+8*r)));
  rotation_aan(x);rotation_transpose16(x);rotation_aan(x);rotation_transpose16(x);
  for(int r=0;r<8;r++){
    rotation_I y=_mm_srai_epi16(rotation_add(x[r],_mm_set1_epi16(1 << (INTEGER_PASS_BITS+2))),INTEGER_PASS_BITS+3);
    y=_mm_add_epi8(_mm_packs_epi16(y,y),_mm_set1_epi8(-128));
    _mm_storel_epi64((rotation_I*)(out+8*r),y);
  }
}

using rotation_J = __m256i;
static inline rotation_J rotation_add2(rotation_J a,rotation_J b){return _mm256_add_epi16(a,b);}
static inline rotation_J rotation_sub2(rotation_J a,rotation_J b){return _mm256_sub_epi16(a,b);}
// Fractional multiplies round to nearest, ties toward positive infinity;
// integer additions supply the whole part of sqrt(2)*x, avoiding IFAST's pre-multiply
// left shift (which discards the top two bits). Q15 fractions are derived
// by rounding the real constants, not by rescaling IFAST's 8-bit constants.
static inline rotation_J rotation_frac2(rotation_J x,int c){return _mm256_mulhrs_epi16(x,_mm256_set1_epi16(c));}
static inline rotation_J rotation_root22(rotation_J x){return rotation_add2(x,rotation_frac2(x,13573));}
static inline void rotation_aan2(rotation_J *x){
  rotation_J p=rotation_add2(x[0],x[4]),q=rotation_sub2(x[0],x[4]);
  rotation_J r=rotation_add2(x[2],x[6]),t=rotation_sub2(rotation_root22(rotation_sub2(x[2],x[6])),r);
  rotation_J e0=rotation_add2(p,r),e3=rotation_sub2(p,r),e1=rotation_add2(q,t),e2=rotation_sub2(q,t);
  rotation_J a=rotation_add2(x[5],x[3]),b=rotation_sub2(x[5],x[3]);
  rotation_J c=rotation_add2(x[1],x[7]),d=rotation_sub2(x[1],x[7]);
  rotation_J o7=rotation_add2(c,a),u=rotation_root22(rotation_sub2(c,a));
  rotation_J v=rotation_sub2(rotation_frac2(d,30274),rotation_frac2(b,12540));
  rotation_J w=rotation_add2(rotation_frac2(b,30274),rotation_frac2(d,12540));
  rotation_J o6=rotation_sub2(rotation_add2(v,v),o7);
  rotation_J o5=rotation_sub2(u,o6),o4=rotation_sub2(rotation_add2(w,w),o5);
  x[0]=rotation_add2(e0,o7);x[7]=rotation_sub2(e0,o7);x[1]=rotation_add2(e1,o6);x[6]=rotation_sub2(e1,o6);
  x[2]=rotation_add2(e2,o5);x[5]=rotation_sub2(e2,o5);x[3]=rotation_add2(e3,o4);x[4]=rotation_sub2(e3,o4);
}
static inline void rotation_transpose162(rotation_J *x){
  rotation_J a[8],b[8];
  for(int i=0;i<4;i++){a[2*i]=_mm256_unpacklo_epi16(x[2*i],x[2*i+1]);a[2*i+1]=_mm256_unpackhi_epi16(x[2*i],x[2*i+1]);}
  for(int i=0;i<2;i++)for(int j=0;j<2;j++){
    b[4*i+j*2]=_mm256_unpacklo_epi32(a[4*i+j],a[4*i+j+2]);
    b[4*i+j*2+1]=_mm256_unpackhi_epi32(a[4*i+j],a[4*i+j+2]);
  }
  for(int i=0;i<4;i++){x[2*i]=_mm256_unpacklo_epi64(b[i],b[i+4]);x[2*i+1]=_mm256_unpackhi_epi64(b[i],b[i+4]);}
}

__attribute__((noinline)) static void rotation_candidate2(const Block *b,const short *q,unsigned char *out){
  rotation_J x[8];for(int r=0;r<8;r++){
    rotation_J v=_mm256_inserti128_si256(_mm256_castsi128_si256(_mm_loadu_si128((const rotation_I*)(b[0].data()+8*r))),_mm_loadu_si128((const rotation_I*)(b[1].data()+8*r)),1);
    x[r]=_mm256_mullo_epi16(v,_mm256_broadcastsi128_si256(_mm_loadu_si128((const rotation_I*)(q+8*r))));
  }
  rotation_aan2(x);rotation_transpose162(x);rotation_aan2(x);rotation_transpose162(x);
  for(int r=0;r<8;r++){
    rotation_J y=_mm256_srai_epi16(rotation_add2(x[r],_mm256_set1_epi16(1 << (INTEGER_PASS_BITS+2))),INTEGER_PASS_BITS+3);
    y=_mm256_add_epi8(_mm256_packs_epi16(y,y),_mm256_set1_epi8(-128));
    _mm_storel_epi64((rotation_I*)(out+8*r),_mm256_castsi256_si128(y));
    _mm_storel_epi64((rotation_I*)(out+64+8*r),_mm256_extracti128_si256(y,1));
  }
}

// Wide arithmetic oracle. Clipped output agreement alone does not prove
// absence of intermediate overflow; the admission bound supplies that proof.
static void rotation_wide(const Block *b,const short *q,unsigned char *out){
  long long w[64];for(int k=0;k<64;k++)w[k]=static_cast<long long>(b->at(k))*q[k];
  auto f=[](long long x,int c){return (x*c+16384)>>15;};
  auto transform=[&](long long *x,int s){
    auto root=[&](long long x){return x+f(x,13573);};
    auto p=x[0]+x[4*s],q=x[0]-x[4*s],r=x[2*s]+x[6*s];
    auto t=root(x[2*s]-x[6*s])-r;
    auto e0=p+r,e3=p-r,e1=q+t,e2=q-t;
    auto a=x[5*s]+x[3*s],b=x[5*s]-x[3*s];
    auto c=x[s]+x[7*s],d=x[s]-x[7*s];
    auto o7=c+a,u=root(c-a);
    auto v=f(d,30274)-f(b,12540),w=f(b,30274)+f(d,12540);
    auto o6=(v+v)-o7,o5=u-o6,o4=(w+w)-o5;
    x[0]=e0+o7;x[7*s]=e0-o7;x[s]=e1+o6;x[6*s]=e1-o6;
    x[2*s]=e2+o5;x[5*s]=e2-o5;x[3*s]=e3+o4;x[4*s]=e3-o4;
  };
  for(int c=0;c<8;c++)transform(w+c,8);
  for(int r=0;r<8;r++)transform(w+8*r,1);
  for(int k=0;k<64;k++)out[k]=std::clamp<long long>(((w[k]+(1<<(INTEGER_PASS_BITS+2)))>>(INTEGER_PASS_BITS+3))+128,0,255);
}

// Conservative per-coefficient gains, derived for EVERY operation in both
// passes (including multiply arguments), rounded upward to integers.
static constexpr short rotation_weights[64]={
  1,2,2,2,1,2,3,6,
  2,2,2,2,2,2,3,6,
  2,2,2,2,2,2,3,6,
  2,3,2,3,2,3,3,6,
  1,2,2,2,1,2,3,6,
  2,4,3,4,2,4,5,9,
  3,5,4,5,3,5,6,13,
  6,10,8,10,6,10,13,26
};
struct RotationGuard {
  alignas(32) short weighted_quant[64];
  bool usable=true;
  explicit RotationGuard(const short *q){
    for(int k=0;k<64;k++){
      int v=int(q[k])*rotation_weights[k];
      if(q[k]<0 || v>32767)usable=false;
      weighted_quant[k]=short(std::min(std::max(v,0),32767));
    }
  }
};
static inline bool rotation_admit(const Block *b,const RotationGuard &g){
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
  // Error <=113 plus final rounding bias.  Symmetric limit is 32767.
  constexpr int limit=32767-113-(1<<(INTEGER_PASS_BITS+2));
  return _mm_cvtsi128_si32(t)<=limit;
}
__attribute__((noinline)) static void rotation_safe2(const Block *b,const short *q,
                                                  const RotationGuard &g,unsigned char *out){
  bool a=rotation_admit(b,g),c=rotation_admit(b+1,g);
  if(a&&c){rotation_candidate2(b,q,out);return;}
  if(a)rotation_candidate(b,q,out);else rotation_wide(b,q,out);
  if(c)rotation_candidate(b+1,q,out+64);else rotation_wide(b+1,q,out+64);
}
