#ifndef INTEGER_PASS_BITS
#define INTEGER_PASS_BITS 2
#endif
static_assert(INTEGER_PASS_BITS>=2 && INTEGER_PASS_BITS<=4,"supported precision is 2..4");
// Experimental integer approximation of the scaled cosine transform.
// Shares the AAN real-valued factorization with float4, but not IFAST's
// constants, multiply truncation, or prescaling.  All arithmetic wraps at 16
// bits, except rounded fractional multiplies and the final saturating store.
using I = __m128i;
static inline I add(I a,I b){return _mm_add_epi16(a,b);}
static inline I sub(I a,I b){return _mm_sub_epi16(a,b);}
// c*x = floor(c)*x + round(frac(c)*x), avoiding IFAST's pre-multiply
// left shift (which discards the top two bits). Q15 fractions are derived
// by rounding the real constants, not by rescaling IFAST's 8-bit constants.
static inline I frac(I x,int c){return _mm_mulhrs_epi16(x,_mm_set1_epi16(c));}
static inline I root2(I x){return add(x,frac(x,13573));}
static inline void integer_aan(I *x){
  I p=add(x[0],x[4]),q=sub(x[0],x[4]);
  I r=add(x[2],x[6]),t=sub(root2(sub(x[2],x[6])),r);
  I e0=add(p,r),e3=sub(p,r),e1=add(q,t),e2=sub(q,t);
  I a=add(x[5],x[3]),b=sub(x[5],x[3]);
  I c=add(x[1],x[7]),d=sub(x[1],x[7]);
  I o7=add(c,a),u=root2(sub(c,a));
  I bd=add(b,d),z=add(bd,frac(bd,27779));
  I o6=sub(sub(z,add(add(b,b),frac(b,20091))),o7);
  I o5=sub(u,o6),o4=sub(sub(z,add(d,frac(d,2700))),o5);
  x[0]=add(e0,o7);x[7]=sub(e0,o7);x[1]=add(e1,o6);x[6]=sub(e1,o6);
  x[2]=add(e2,o5);x[5]=sub(e2,o5);x[3]=add(e3,o4);x[4]=sub(e3,o4);
}
static inline void transpose16(I *x){
  I a[8],b[8];
  for(int i=0;i<4;i++){a[2*i]=_mm_unpacklo_epi16(x[2*i],x[2*i+1]);a[2*i+1]=_mm_unpackhi_epi16(x[2*i],x[2*i+1]);}
  for(int i=0;i<2;i++)for(int j=0;j<2;j++){
    b[4*i+j*2]=_mm_unpacklo_epi32(a[4*i+j],a[4*i+j+2]);
    b[4*i+j*2+1]=_mm_unpackhi_epi32(a[4*i+j],a[4*i+j+2]);
  }
  for(int i=0;i<4;i++){x[2*i]=_mm_unpacklo_epi64(b[i],b[i+4]);x[2*i+1]=_mm_unpackhi_epi64(b[i],b[i+4]);}
}
__attribute__((noinline)) static void integer_candidate(const Block *b,const short *q,unsigned char *out){
  I x[8];for(int r=0;r<8;r++)x[r]=_mm_mullo_epi16(_mm_loadu_si128((const I*)(b->data()+8*r)),_mm_loadu_si128((const I*)(q+8*r)));
  integer_aan(x);transpose16(x);integer_aan(x);transpose16(x);
  for(int r=0;r<8;r++){
    I y=_mm_srai_epi16(add(x[r],_mm_set1_epi16(1 << (INTEGER_PASS_BITS+2))),INTEGER_PASS_BITS+3);
    y=_mm_add_epi8(_mm_packs_epi16(y,y),_mm_set1_epi8(-128));
    _mm_storel_epi64((I*)(out+8*r),y);
  }
}

using J = __m256i;
static inline J add2(J a,J b){return _mm256_add_epi16(a,b);}
static inline J sub2(J a,J b){return _mm256_sub_epi16(a,b);}
// c*x = floor(c)*x + round(frac2(c)*x), avoiding IFAST's pre-multiply
// left shift (which discards the top two bits). Q15 fractions are derived
// by rounding the real constants, not by rescaling IFAST's 8-bit constants.
static inline J frac2(J x,int c){return _mm256_mulhrs_epi16(x,_mm256_set1_epi16(c));}
static inline J root22(J x){return add2(x,frac2(x,13573));}
static inline void integer_aan2(J *x){
  J p=add2(x[0],x[4]),q=sub2(x[0],x[4]);
  J r=add2(x[2],x[6]),t=sub2(root22(sub2(x[2],x[6])),r);
  J e0=add2(p,r),e3=sub2(p,r),e1=add2(q,t),e2=sub2(q,t);
  J a=add2(x[5],x[3]),b=sub2(x[5],x[3]);
  J c=add2(x[1],x[7]),d=sub2(x[1],x[7]);
  J o7=add2(c,a),u=root22(sub2(c,a));
  J bd=add2(b,d),z=add2(bd,frac2(bd,27779));
  J o6=sub2(sub2(z,add2(add2(b,b),frac2(b,20091))),o7);
  J o5=sub2(u,o6),o4=sub2(sub2(z,add2(d,frac2(d,2700))),o5);
  x[0]=add2(e0,o7);x[7]=sub2(e0,o7);x[1]=add2(e1,o6);x[6]=sub2(e1,o6);
  x[2]=add2(e2,o5);x[5]=sub2(e2,o5);x[3]=add2(e3,o4);x[4]=sub2(e3,o4);
}
static inline void transpose162(J *x){
  J a[8],b[8];
  for(int i=0;i<4;i++){a[2*i]=_mm256_unpacklo_epi16(x[2*i],x[2*i+1]);a[2*i+1]=_mm256_unpackhi_epi16(x[2*i],x[2*i+1]);}
  for(int i=0;i<2;i++)for(int j=0;j<2;j++){
    b[4*i+j*2]=_mm256_unpacklo_epi32(a[4*i+j],a[4*i+j+2]);
    b[4*i+j*2+1]=_mm256_unpackhi_epi32(a[4*i+j],a[4*i+j+2]);
  }
  for(int i=0;i<4;i++){x[2*i]=_mm256_unpacklo_epi64(b[i],b[i+4]);x[2*i+1]=_mm256_unpackhi_epi64(b[i],b[i+4]);}
}

__attribute__((noinline)) static void integer_candidate2(const Block *b,const short *q,unsigned char *out){
  J x[8];for(int r=0;r<8;r++){
    J v=_mm256_inserti128_si256(_mm256_castsi128_si256(_mm_loadu_si128((const I*)(b[0].data()+8*r))),_mm_loadu_si128((const I*)(b[1].data()+8*r)),1);
    x[r]=_mm256_mullo_epi16(v,_mm256_broadcastsi128_si256(_mm_loadu_si128((const I*)(q+8*r))));
  }
  integer_aan2(x);transpose162(x);integer_aan2(x);transpose162(x);
  for(int r=0;r<8;r++){
    J y=_mm256_srai_epi16(add2(x[r],_mm256_set1_epi16(1 << (INTEGER_PASS_BITS+2))),INTEGER_PASS_BITS+3);
    y=_mm256_add_epi8(_mm256_packs_epi16(y,y),_mm256_set1_epi8(-128));
    _mm_storel_epi64((I*)(out+8*r),_mm256_castsi256_si128(y));
    _mm_storel_epi64((I*)(out+64+8*r),_mm256_extracti128_si256(y,1));
  }
}

// Wide arithmetic oracle. Clipped output agreement alone does not prove
// absence of intermediate overflow; the admission bound supplies that proof.
static void integer_wide(const Block *b,const short *q,unsigned char *out){
  long long w[64];for(int k=0;k<64;k++)w[k]=static_cast<long long>(b->at(k))*q[k];
  auto f=[](long long x,int c){return (x*c+16384)>>15;};
  auto transform=[&](long long *x,int s){
    auto root=[&](long long x){return x+f(x,13573);};
    auto p=x[0]+x[4*s],q=x[0]-x[4*s],r=x[2*s]+x[6*s];
    auto t=root(x[2*s]-x[6*s])-r;
    auto e0=p+r,e3=p-r,e1=q+t,e2=q-t;
    auto a=x[5*s]+x[3*s],b=x[5*s]-x[3*s];
    auto c=x[s]+x[7*s],d=x[s]-x[7*s];
    auto o7=c+a,u=root(c-a),bd=b+d,z=bd+f(bd,27779);
    auto o6=z-(2*b+f(b,20091))-o7,o5=u-o6,o4=z-(d+f(d,2700))-o5;
    x[0]=e0+o7;x[7*s]=e0-o7;x[s]=e1+o6;x[6*s]=e1-o6;
    x[2*s]=e2+o5;x[5*s]=e2-o5;x[3*s]=e3+o4;x[4*s]=e3-o4;
  };
  for(int c=0;c<8;c++)transform(w+c,8);
  for(int r=0;r<8;r++)transform(w+8*r,1);
  for(int k=0;k<64;k++)out[k]=std::clamp<long long>(((w[k]+(1<<(INTEGER_PASS_BITS+2)))>>(INTEGER_PASS_BITS+3))+128,0,255);
}

// Conservative per-coefficient gains, derived for EVERY operation in both
// passes (including multiply arguments), rounded upward to integers.
static constexpr short integer_weights[64]={
  1,2,2,3,1,3,3,6, 2,2,2,3,2,3,3,6,
  2,2,2,3,2,3,3,6, 3,3,3,4,3,4,3,6,
  1,2,2,3,1,3,3,6, 3,4,3,5,3,5,5,9,
  3,5,4,7,3,7,6,13, 6,10,8,14,6,14,13,26
};
struct IntegerGuard {
  alignas(32) short weighted_quant[64];
  bool usable=true;
  explicit IntegerGuard(const short *q){
    for(int k=0;k<64;k++){
      int v=int(q[k])*integer_weights[k];
      if(q[k]<0 || v>32767)usable=false;
      weighted_quant[k]=short(std::min(std::max(v,0),32767));
    }
  }
};
static inline bool integer_admit(const Block *b,const IntegerGuard &g){
  if(!g.usable)return false;
  J sums=_mm256_setzero_si256(),negative=sums;
  for(int k=0;k<64;k+=16){
    J a=_mm256_abs_epi16(_mm256_loadu_si256((const J*)(b->data()+k)));
    negative=_mm256_or_si256(negative,a);
    J p=_mm256_madd_epi16(a,_mm256_load_si256((const J*)(g.weighted_quant+k)));
    // Clamp partial sums before adding so even enormous inputs cannot wrap.
    J packed=_mm256_packus_epi32(p,_mm256_setzero_si256());
    sums=_mm256_adds_epu16(sums,packed);
  }
  if(_mm256_movemask_epi8(_mm256_cmpgt_epi16(_mm256_setzero_si256(),negative)))return false;
  sums=_mm256_min_epu16(sums,_mm256_set1_epi16(32767));
  sums=_mm256_madd_epi16(sums,_mm256_set1_epi16(1));
  I t=_mm_add_epi32(_mm256_castsi256_si128(sums),_mm256_extracti128_si256(sums,1));
  t=_mm_hadd_epi32(t,t);t=_mm_hadd_epi32(t,t);
  // Error <=92.075 plus final rounding bias.  Symmetric limit is 32767.
  constexpr int limit=32767-93-(1<<(INTEGER_PASS_BITS+2));
  return _mm_cvtsi128_si32(t)<=limit;
}
__attribute__((noinline)) static void integer_safe2(const Block *b,const short *q,
                                                  const IntegerGuard &g,unsigned char *out){
  bool a=integer_admit(b,g),c=integer_admit(b+1,g);
  if(a&&c){integer_candidate2(b,q,out);return;}
  if(a)integer_candidate(b,q,out);else integer_wide(b,q,out);
  if(c)integer_candidate(b+1,q,out+64);else integer_wide(b+1,q,out+64);
}
