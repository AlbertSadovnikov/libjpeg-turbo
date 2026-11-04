#pragma once
// Coefficient support shortcut: full 8x8 output, not a scaled-down IDCT.
static inline bool rotation_low4_only(const Block &b){
  __m256i mask=_mm256_setr_epi16(0,0,0,0,-1,-1,-1,-1,0,0,0,0,-1,-1,-1,-1);
  __m256i a=_mm256_or_si256(_mm256_loadu_si256((const __m256i*)b.data()),_mm256_loadu_si256((const __m256i*)(b.data()+16)));
  a=_mm256_and_si256(a,mask);
  a=_mm256_or_si256(a,_mm256_loadu_si256((const __m256i*)(b.data()+32)));
  a=_mm256_or_si256(a,_mm256_loadu_si256((const __m256i*)(b.data()+48)));
  return _mm256_testz_si256(a,a);
}
static inline void rotation_low4_aan(rotation_I *x){
  rotation_I t=rotation_frac(x[2],13573);
  rotation_I e0=rotation_add(x[0],x[2]),e3=rotation_sub(x[0],x[2]);
  rotation_I e1=rotation_add(x[0],t),e2=rotation_sub(x[0],t);
  rotation_I b=rotation_sub(_mm_setzero_si128(),x[3]);
  rotation_I o7=rotation_add(x[1],x[3]),u=rotation_root2(rotation_sub(x[1],x[3]));
  rotation_I v=rotation_sub(rotation_frac(x[1],30274),rotation_frac(b,12540));
  rotation_I w=rotation_add(rotation_frac(b,30274),rotation_frac(x[1],12540));
  rotation_I o6=rotation_sub(rotation_add(v,v),o7);
  rotation_I o5=rotation_sub(u,o6),o4=rotation_sub(rotation_add(w,w),o5);
  x[0]=rotation_add(e0,o7);x[7]=rotation_sub(e0,o7);x[1]=rotation_add(e1,o6);x[6]=rotation_sub(e1,o6);
  x[2]=rotation_add(e2,o5);x[5]=rotation_sub(e2,o5);x[3]=rotation_add(e3,o4);x[4]=rotation_sub(e3,o4);
}
static inline void rotation_low4_transpose(rotation_I *x){
  rotation_I a[4],b[4];
  for(int i=0;i<4;i++)a[i]=_mm_unpacklo_epi16(x[2*i],x[2*i+1]);
  b[0]=_mm_unpacklo_epi32(a[0],a[1]);b[1]=_mm_unpackhi_epi32(a[0],a[1]);
  b[2]=_mm_unpacklo_epi32(a[2],a[3]);b[3]=_mm_unpackhi_epi32(a[2],a[3]);
  x[0]=_mm_unpacklo_epi64(b[0],b[2]);x[1]=_mm_unpackhi_epi64(b[0],b[2]);
  x[2]=_mm_unpacklo_epi64(b[1],b[3]);x[3]=_mm_unpackhi_epi64(b[1],b[3]);
}
static inline void rotation_low4_aan2(rotation_J *x){
  rotation_J t=rotation_frac2(x[2],13573);
  rotation_J e0=rotation_add2(x[0],x[2]),e3=rotation_sub2(x[0],x[2]);
  rotation_J e1=rotation_add2(x[0],t),e2=rotation_sub2(x[0],t);
  rotation_J b=rotation_sub2(_mm256_setzero_si256(),x[3]);
  rotation_J o7=rotation_add2(x[1],x[3]),u=rotation_root22(rotation_sub2(x[1],x[3]));
  rotation_J v=rotation_sub2(rotation_frac2(x[1],30274),rotation_frac2(b,12540));
  rotation_J w=rotation_add2(rotation_frac2(b,30274),rotation_frac2(x[1],12540));
  rotation_J o6=rotation_sub2(rotation_add2(v,v),o7);
  rotation_J o5=rotation_sub2(u,o6),o4=rotation_sub2(rotation_add2(w,w),o5);
  x[0]=rotation_add2(e0,o7);x[7]=rotation_sub2(e0,o7);x[1]=rotation_add2(e1,o6);x[6]=rotation_sub2(e1,o6);
  x[2]=rotation_add2(e2,o5);x[5]=rotation_sub2(e2,o5);x[3]=rotation_add2(e3,o4);x[4]=rotation_sub2(e3,o4);
}
static inline void rotation_low4_transpose2(rotation_J *x){
  rotation_J a[4],b[4];
  for(int i=0;i<4;i++)a[i]=_mm256_unpacklo_epi16(x[2*i],x[2*i+1]);
  b[0]=_mm256_unpacklo_epi32(a[0],a[1]);b[1]=_mm256_unpackhi_epi32(a[0],a[1]);
  b[2]=_mm256_unpacklo_epi32(a[2],a[3]);b[3]=_mm256_unpackhi_epi32(a[2],a[3]);
  x[0]=_mm256_unpacklo_epi64(b[0],b[2]);x[1]=_mm256_unpackhi_epi64(b[0],b[2]);
  x[2]=_mm256_unpacklo_epi64(b[1],b[3]);x[3]=_mm256_unpackhi_epi64(b[1],b[3]);
}
__attribute__((noinline)) static void rotation_low4_candidate(const Block *b,const short *q,unsigned char *out){
  rotation_I x[8];for(int r=0;r<4;r++)x[r]=_mm_mullo_epi16(_mm_loadl_epi64((const rotation_I*)(b->data()+8*r)),_mm_loadl_epi64((const rotation_I*)(q+8*r)));
  rotation_low4_aan(x);rotation_low4_transpose(x);rotation_low4_aan(x);rotation_transpose16(x);
  for(int r=0;r<8;r++){
    rotation_I y=_mm_srai_epi16(rotation_add(x[r],_mm_set1_epi16(1 << (INTEGER_PASS_BITS+2))),INTEGER_PASS_BITS+3);
    y=_mm_add_epi8(_mm_packs_epi16(y,y),_mm_set1_epi8(-128));
    _mm_storel_epi64((rotation_I*)(out+8*r),y);
  }
}
__attribute__((noinline)) static void rotation_low4_candidate2(const Block *b,const short *q,unsigned char *out){
  rotation_J x[8];for(int r=0;r<4;r++){
    rotation_J v=_mm256_inserti128_si256(_mm256_castsi128_si256(_mm_loadl_epi64((const rotation_I*)(b[0].data()+8*r))),_mm_loadl_epi64((const rotation_I*)(b[1].data()+8*r)),1);
    x[r]=_mm256_mullo_epi16(v,_mm256_broadcastsi128_si256(_mm_loadl_epi64((const rotation_I*)(q+8*r))));
  }
  rotation_low4_aan2(x);rotation_low4_transpose2(x);rotation_low4_aan2(x);rotation_transpose162(x);
  for(int r=0;r<8;r++){
    rotation_J y=_mm256_srai_epi16(rotation_add2(x[r],_mm256_set1_epi16(1 << (INTEGER_PASS_BITS+2))),INTEGER_PASS_BITS+3);
    y=_mm256_add_epi8(_mm256_packs_epi16(y,y),_mm256_set1_epi8(-128));
    _mm_storel_epi64((rotation_I*)(out+8*r),_mm256_castsi256_si128(y));
    _mm_storel_epi64((rotation_I*)(out+64+8*r),_mm256_extracti128_si256(y,1));
  }
}


// Pair-only policy retains the dense pair kernel on mixed-support pairs.
// Mixed policy permits a reduced single-block kernel when only one qualifies.
template<bool Mixed>
__attribute__((noinline)) static void rotation_low4_safe2(const Block *b,const short *q,
                                                         const RotationGuard &g,unsigned char *out){
  bool a=rotation_low4_only(b[0]),c=rotation_low4_only(b[1]);
  if((!a&&!c) || (!Mixed && a!=c)){rotation_safe2(b,q,g,out);return;}
  bool sa=rotation_admit(b,g),sc=rotation_admit(b+1,g);
  if(a&&c&&sa&&sc){rotation_low4_candidate2(b,q,out);return;}
  if(sa){if(a)rotation_low4_candidate(b,q,out);else rotation_candidate(b,q,out);}
  else rotation_wide(b,q,out);
  if(sc){if(c)rotation_low4_candidate(b+1,q,out+64);else rotation_candidate(b+1,q,out+64);}
  else rotation_wide(b+1,q,out+64);
}
