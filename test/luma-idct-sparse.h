#pragma once
// DC-only classification includes coefficient scanning in timed execution.
static inline bool rotation_dc_only(const Block &b){
  if(b[1] || b[8])return false;
  const __m256i keep=_mm256_setr_epi16(0,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1);
  __m256i a=_mm256_and_si256(_mm256_loadu_si256((const __m256i*)b.data()),keep);
  for(int k=16;k<64;k+=16)a=_mm256_or_si256(a,_mm256_loadu_si256((const __m256i*)(b.data()+k)));
  return _mm256_testz_si256(a,a);
}
static inline void rotation_dc_store(const Block &b,const short *q,unsigned char *out){
  // For signed-short inputs, the product and bias fit in signed 32 bits.
  int v=(int(b[0])*int(q[0])+(1<<(INTEGER_PASS_BITS+2)))>>(INTEGER_PASS_BITS+3);
  v=std::clamp(v+128,0,255);
  __m256i pixels=_mm256_set1_epi8(static_cast<char>(v));
  _mm256_storeu_si256((__m256i*)out,pixels);
  _mm256_storeu_si256((__m256i*)(out+32),pixels);
}
__attribute__((noinline)) static void rotation_dc_safe2(const Block *b,const short *q,
                                                       const RotationGuard &g,unsigned char *out){
  bool a=rotation_dc_only(b[0]),c=rotation_dc_only(b[1]);
  if(!a&&!c){rotation_safe2(b,q,g,out);return;}
  if(a)rotation_dc_store(b[0],q,out);
  else if(rotation_admit(b,g))rotation_candidate(b,q,out);
  else rotation_wide(b,q,out);
  if(c)rotation_dc_store(b[1],q,out+64);
  else if(rotation_admit(b+1,g))rotation_candidate(b+1,q,out+64);
  else rotation_wide(b+1,q,out+64);
}
