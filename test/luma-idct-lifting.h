#pragma once
// Three-shear odd-part rotation. Q15 tan(pi/16)=6518, sin(pi/8)=12540.
// d1=d-round(t*b); w=b+round(s*d1); v=d1-round(t*w).
// Rounding is per shear, so this is a different integer approximation.
#ifndef INTEGER_PASS_BITS
#define INTEGER_PASS_BITS 2
#endif
static_assert(INTEGER_PASS_BITS>=2 && INTEGER_PASS_BITS<=4,"supported precision is 2..4");
// Experimental integer approximation of the scaled cosine transform.
// Shares the AAN real-valued factorization with float4, but not IFAST's
// constants, multiply truncation, or prescaling.  All arithmetic wraps at 16
// bits, except rounded fractional multiplies and the final saturating store.
using lifting_I = __m128i;
static inline lifting_I lifting_add(lifting_I a,lifting_I b){return _mm_add_epi16(a,b);}
static inline lifting_I lifting_sub(lifting_I a,lifting_I b){return _mm_sub_epi16(a,b);}
// Fractional multiplies round to nearest, ties toward positive infinity;
// integer additions supply the whole part of sqrt(2)*x, avoiding IFAST's pre-multiply
// left shift (which discards the top two bits). Q15 fractions are derived
// by rounding the real constants, not by rescaling IFAST's 8-bit constants.
static inline lifting_I lifting_frac(lifting_I x,int c){return _mm_mulhrs_epi16(x,_mm_set1_epi16(c));}
static inline lifting_I lifting_root2(lifting_I x){return lifting_add(x,lifting_frac(x,13573));}
static inline void lifting_aan(lifting_I *x){
  lifting_I p=lifting_add(x[0],x[4]),q=lifting_sub(x[0],x[4]);
  lifting_I r=lifting_add(x[2],x[6]),t=lifting_sub(lifting_root2(lifting_sub(x[2],x[6])),r);
  lifting_I e0=lifting_add(p,r),e3=lifting_sub(p,r),e1=lifting_add(q,t),e2=lifting_sub(q,t);
  lifting_I a=lifting_add(x[5],x[3]),b=lifting_sub(x[5],x[3]);
  lifting_I c=lifting_add(x[1],x[7]),d=lifting_sub(x[1],x[7]);
  lifting_I o7=lifting_add(c,a),u=lifting_root2(lifting_sub(c,a));
  lifting_I d1=lifting_sub(d,lifting_frac(b,6518));
  lifting_I w=lifting_add(b,lifting_frac(d1,12540));
  lifting_I v=lifting_sub(d1,lifting_frac(w,6518));
  lifting_I o6=lifting_sub(lifting_add(v,v),o7);
  lifting_I o5=lifting_sub(u,o6),o4=lifting_sub(lifting_add(w,w),o5);
  x[0]=lifting_add(e0,o7);x[7]=lifting_sub(e0,o7);x[1]=lifting_add(e1,o6);x[6]=lifting_sub(e1,o6);
  x[2]=lifting_add(e2,o5);x[5]=lifting_sub(e2,o5);x[3]=lifting_add(e3,o4);x[4]=lifting_sub(e3,o4);
}
static inline void lifting_transpose16(lifting_I *x){
  lifting_I a[8],b[8];
  for(int i=0;i<4;i++){a[2*i]=_mm_unpacklo_epi16(x[2*i],x[2*i+1]);a[2*i+1]=_mm_unpackhi_epi16(x[2*i],x[2*i+1]);}
  for(int i=0;i<2;i++)for(int j=0;j<2;j++){
    b[4*i+j*2]=_mm_unpacklo_epi32(a[4*i+j],a[4*i+j+2]);
    b[4*i+j*2+1]=_mm_unpackhi_epi32(a[4*i+j],a[4*i+j+2]);
  }
  for(int i=0;i<4;i++){x[2*i]=_mm_unpacklo_epi64(b[i],b[i+4]);x[2*i+1]=_mm_unpackhi_epi64(b[i],b[i+4]);}
}
__attribute__((noinline)) static void lifting_candidate(const Block *b,const short *q,unsigned char *out){
  lifting_I x[8];for(int r=0;r<8;r++)x[r]=_mm_mullo_epi16(_mm_loadu_si128((const lifting_I*)(b->data()+8*r)),_mm_loadu_si128((const lifting_I*)(q+8*r)));
  lifting_aan(x);lifting_transpose16(x);lifting_aan(x);lifting_transpose16(x);
  for(int r=0;r<8;r++){
    lifting_I y=_mm_srai_epi16(lifting_add(x[r],_mm_set1_epi16(1 << (INTEGER_PASS_BITS+2))),INTEGER_PASS_BITS+3);
    y=_mm_add_epi8(_mm_packs_epi16(y,y),_mm_set1_epi8(-128));
    _mm_storel_epi64((lifting_I*)(out+8*r),y);
  }
}

using lifting_J = __m256i;
static inline lifting_J lifting_add2(lifting_J a,lifting_J b){return _mm256_add_epi16(a,b);}
static inline lifting_J lifting_sub2(lifting_J a,lifting_J b){return _mm256_sub_epi16(a,b);}
// Fractional multiplies round to nearest, ties toward positive infinity;
// integer additions supply the whole part of sqrt(2)*x, avoiding IFAST's pre-multiply
// left shift (which discards the top two bits). Q15 fractions are derived
// by rounding the real constants, not by rescaling IFAST's 8-bit constants.
static inline lifting_J lifting_frac2(lifting_J x,int c){return _mm256_mulhrs_epi16(x,_mm256_set1_epi16(c));}
static inline lifting_J lifting_root22(lifting_J x){return lifting_add2(x,lifting_frac2(x,13573));}
static inline void lifting_aan2(lifting_J *x){
  lifting_J p=lifting_add2(x[0],x[4]),q=lifting_sub2(x[0],x[4]);
  lifting_J r=lifting_add2(x[2],x[6]),t=lifting_sub2(lifting_root22(lifting_sub2(x[2],x[6])),r);
  lifting_J e0=lifting_add2(p,r),e3=lifting_sub2(p,r),e1=lifting_add2(q,t),e2=lifting_sub2(q,t);
  lifting_J a=lifting_add2(x[5],x[3]),b=lifting_sub2(x[5],x[3]);
  lifting_J c=lifting_add2(x[1],x[7]),d=lifting_sub2(x[1],x[7]);
  lifting_J o7=lifting_add2(c,a),u=lifting_root22(lifting_sub2(c,a));
  lifting_J d1=lifting_sub2(d,lifting_frac2(b,6518));
  lifting_J w=lifting_add2(b,lifting_frac2(d1,12540));
  lifting_J v=lifting_sub2(d1,lifting_frac2(w,6518));
  lifting_J o6=lifting_sub2(lifting_add2(v,v),o7);
  lifting_J o5=lifting_sub2(u,o6),o4=lifting_sub2(lifting_add2(w,w),o5);
  x[0]=lifting_add2(e0,o7);x[7]=lifting_sub2(e0,o7);x[1]=lifting_add2(e1,o6);x[6]=lifting_sub2(e1,o6);
  x[2]=lifting_add2(e2,o5);x[5]=lifting_sub2(e2,o5);x[3]=lifting_add2(e3,o4);x[4]=lifting_sub2(e3,o4);
}
static inline void lifting_transpose162(lifting_J *x){
  lifting_J a[8],b[8];
  for(int i=0;i<4;i++){a[2*i]=_mm256_unpacklo_epi16(x[2*i],x[2*i+1]);a[2*i+1]=_mm256_unpackhi_epi16(x[2*i],x[2*i+1]);}
  for(int i=0;i<2;i++)for(int j=0;j<2;j++){
    b[4*i+j*2]=_mm256_unpacklo_epi32(a[4*i+j],a[4*i+j+2]);
    b[4*i+j*2+1]=_mm256_unpackhi_epi32(a[4*i+j],a[4*i+j+2]);
  }
  for(int i=0;i<4;i++){x[2*i]=_mm256_unpacklo_epi64(b[i],b[i+4]);x[2*i+1]=_mm256_unpackhi_epi64(b[i],b[i+4]);}
}

__attribute__((noinline)) static void lifting_candidate2(const Block *b,const short *q,unsigned char *out){
  lifting_J x[8];for(int r=0;r<8;r++){
    lifting_J v=_mm256_inserti128_si256(_mm256_castsi128_si256(_mm_loadu_si128((const lifting_I*)(b[0].data()+8*r))),_mm_loadu_si128((const lifting_I*)(b[1].data()+8*r)),1);
    x[r]=_mm256_mullo_epi16(v,_mm256_broadcastsi128_si256(_mm_loadu_si128((const lifting_I*)(q+8*r))));
  }
  lifting_aan2(x);lifting_transpose162(x);lifting_aan2(x);lifting_transpose162(x);
  for(int r=0;r<8;r++){
    lifting_J y=_mm256_srai_epi16(lifting_add2(x[r],_mm256_set1_epi16(1 << (INTEGER_PASS_BITS+2))),INTEGER_PASS_BITS+3);
    y=_mm256_add_epi8(_mm256_packs_epi16(y,y),_mm256_set1_epi8(-128));
    _mm_storel_epi64((lifting_I*)(out+8*r),_mm256_castsi256_si128(y));
    _mm_storel_epi64((lifting_I*)(out+64+8*r),_mm256_extracti128_si256(y,1));
  }
}

// Wide arithmetic oracle. Clipped output agreement alone does not prove
// absence of intermediate overflow; the admission bound supplies that proof.
static void lifting_wide(const Block *b,const short *q,unsigned char *out){
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
    auto d1=d-f(b,6518),w=b+f(d1,12540),v=d1-f(w,6518);
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
static constexpr short lifting_weights[64]={
  1,2,2,2,1,2,3,6,
  2,2,2,2,2,2,3,6,
  2,2,2,2,2,2,3,6,
  2,3,2,3,2,3,3,6,
  1,2,2,2,1,2,3,6,
  2,4,3,4,2,4,5,9,
  3,5,4,5,3,5,6,13,
  6,10,8,10,6,10,13,26
};
struct LiftingGuard {
  alignas(32) short weighted_quant[64];
  bool usable=true;
  explicit LiftingGuard(const short *q){
    for(int k=0;k<64;k++){
      int v=int(q[k])*lifting_weights[k];
      if(q[k]<0 || v>32767)usable=false;
      weighted_quant[k]=short(std::min(std::max(v,0),32767));
    }
  }
};
static inline bool lifting_admit(const Block *b,const LiftingGuard &g){
  if(!g.usable)return false;
  lifting_J sums=_mm256_setzero_si256(),negative=sums;
  for(int k=0;k<64;k+=16){
    lifting_J a=_mm256_abs_epi16(_mm256_loadu_si256((const lifting_J*)(b->data()+k)));
    negative=_mm256_or_si256(negative,a);
    lifting_J p=_mm256_madd_epi16(a,_mm256_load_si256((const lifting_J*)(g.weighted_quant+k)));
    // Clamp partial sums before adding so even enormous inputs cannot wrap.
    lifting_J packed=_mm256_packus_epi32(p,_mm256_setzero_si256());
    sums=_mm256_adds_epu16(sums,packed);
  }
  if(_mm256_movemask_epi8(_mm256_cmpgt_epi16(_mm256_setzero_si256(),negative)))return false;
  sums=_mm256_min_epu16(sums,_mm256_set1_epi16(32767));
  sums=_mm256_madd_epi16(sums,_mm256_set1_epi16(1));
  lifting_I t=_mm_add_epi32(_mm256_castsi256_si128(sums),_mm256_extracti128_si256(sums,1));
  t=_mm_hadd_epi32(t,t);t=_mm_hadd_epi32(t,t);
  // Error <=110 plus final rounding bias.  Symmetric limit is 32767.
  constexpr int limit=32767-110-(1<<(INTEGER_PASS_BITS+2));
  return _mm_cvtsi128_si32(t)<=limit;
}
__attribute__((noinline)) static void lifting_safe2(const Block *b,const short *q,
                                                  const LiftingGuard &g,unsigned char *out){
  bool a=lifting_admit(b,g),c=lifting_admit(b+1,g);
  if(a&&c){lifting_candidate2(b,q,out);return;}
  if(a)lifting_candidate(b,q,out);else lifting_wide(b,q,out);
  if(c)lifting_candidate(b+1,q,out+64);else lifting_wide(b+1,q,out+64);
}
