// Experimental x86-64 fused 4:2:2 chroma reconstruction for NV12.
// The horizontal factorization follows the LL&M equations in jidctint.c.
#include <cstdio>
#include <cstddef>
#define JPEG_INTERNALS
#include "jpeglib.h"
#include "fusion.h"
#include <immintrin.h>
#include <cmath>
#include <cstring>

extern "C" void mjpeg_chroma_exact(const void *,const void *,const JCOEF *,const JCOEF *,unsigned char *,int);
struct alignas(32) Context {
  j_decompress_ptr c=nullptr;unsigned char *uv=nullptr;int pitch=0,mode=0;
  bool prepared=false;unsigned short quant[2][64]{};
  alignas(32) float dc[2][8];
  alignas(32) float weight[2][6][4][8];
};
static thread_local Context ctx;
static constexpr int vf[6]={1,2,3,5,6,7};
extern "C" int mjpeg_fusion_begin(j_decompress_ptr c,unsigned char *uv,int pitch,int mode) {
  ctx.c=nullptr;
  if(!mode||!__builtin_cpu_supports("avx2")||!__builtin_cpu_supports("fma")||
     !uv||pitch<int(c->image_width)||c->data_precision!=8||
     !c->raw_data_out||c->num_components!=3||c->comps_in_scan!=3||c->blocks_in_MCU!=4||
     c->jpeg_color_space!=JCS_YCbCr||c->progressive_mode||c->arith_code||
     c->output_width!=c->image_width||c->output_height!=c->image_height||
     c->cur_comp_info[0]!=&c->comp_info[0]||c->cur_comp_info[1]!=&c->comp_info[1]||c->cur_comp_info[2]!=&c->comp_info[2]||
     c->max_h_samp_factor!=2||c->max_v_samp_factor!=1||c->image_width%16||c->image_height%8||
     c->comp_info[0].MCU_width!=2||c->comp_info[1].MCU_width!=1||c->comp_info[2].MCU_width!=1||
     c->comp_info[0].DCT_scaled_size!=8||c->comp_info[1].DCT_scaled_size!=8||c->comp_info[2].DCT_scaled_size!=8||
     (mode==1&&c->dct_method!=JDCT_ISLOW)) return 0;
  bool changed=!ctx.prepared;
  for(int ci=0;ci<2;ci++) {
    auto *q=c->quant_tbl_ptrs[c->comp_info[ci+1].quant_tbl_no];
    if(!q)return 0;
    changed|=std::memcmp(ctx.quant[ci],q->quantval,sizeof(ctx.quant[ci]))!=0;
    std::memcpy(ctx.quant[ci],q->quantval,sizeof(ctx.quant[ci]));
  }
  if(changed) {
    const double pi=std::acos(-1.0);
    for(int half=0;half<2;half++)for(int lane=0;lane<8;lane++) {
      int ci=lane/4,u=half*4+lane%4;ctx.dc[half][lane]=ctx.quant[ci][u];
      for(int j=0;j<6;j++)for(int y=0;y<4;y++) {
        int v=vf[j];
        double w=std::sqrt(2.0)*std::cos(v*pi/16)*std::cos((2*y+1)*v*pi/8);
        ctx.weight[half][j][y][lane]=float(w*ctx.quant[ci][v*8+u]);
      }
    }
    ctx.prepared=true;
  }
  ctx.c=c;ctx.uv=uv;ctx.pitch=pitch;ctx.mode=mode;return 1;
}
extern "C" void mjpeg_fusion_end(){ctx.c=nullptr;}

__attribute__((target("avx2,fma")))
static inline __m256 coefficients(const JCOEF *cb,const JCOEF *cr,int v,int half) {
  auto a=_mm_cvtepi16_epi32(_mm_loadl_epi64((const __m128i *)(cb+v*8+half*4)));
  auto b=_mm_cvtepi16_epi32(_mm_loadl_epi64((const __m128i *)(cr+v*8+half*4)));
  return _mm256_cvtepi32_ps(_mm256_inserti128_si256(_mm256_castsi128_si256(a),b,1));
}
__attribute__((target("avx2,fma")))
static inline void transpose4(__m256 a,__m256 b,__m256 c,__m256 d,__m256 *out) {
  auto t0=_mm256_unpacklo_ps(a,b),t1=_mm256_unpackhi_ps(a,b);
  auto t2=_mm256_unpacklo_ps(c,d),t3=_mm256_unpackhi_ps(c,d);
  out[0]=_mm256_shuffle_ps(t0,t2,0x44);out[1]=_mm256_shuffle_ps(t0,t2,0xee);
  out[2]=_mm256_shuffle_ps(t1,t3,0x44);out[3]=_mm256_shuffle_ps(t1,t3,0xee);
}
__attribute__((target("avx2,fma")))
static void reduced(const JCOEF *cb,const JCOEF *cr,unsigned char *uv,int pitch) {
  __m256 f[8];
  for(int half=0;half<2;half++) {
    __m256 a=_mm256_mul_ps(coefficients(cb,cr,0,half),_mm256_load_ps(ctx.dc[half]));
    __m256 b=a,c=a,d=a;
    for(int j=0;j<6;j++) {
      auto x=coefficients(cb,cr,vf[j],half);
      a=_mm256_fmadd_ps(x,_mm256_load_ps(ctx.weight[half][j][0]),a);
      b=_mm256_fmadd_ps(x,_mm256_load_ps(ctx.weight[half][j][1]),b);
      c=_mm256_fmadd_ps(x,_mm256_load_ps(ctx.weight[half][j][2]),c);
      d=_mm256_fmadd_ps(x,_mm256_load_ps(ctx.weight[half][j][3]),d);
    }
    transpose4(a,b,c,d,f+half*4);
  }
  auto add=[](__m256 a,__m256 b){return _mm256_add_ps(a,b);};
  auto sub=[](__m256 a,__m256 b){return _mm256_sub_ps(a,b);};
  auto mul=[](__m256 a,float k){return _mm256_mul_ps(a,_mm256_set1_ps(k));};
  auto z1=mul(add(f[2],f[6]),0.541196100f);
  auto t2=add(z1,mul(f[6],-1.847759065f)),t3=add(z1,mul(f[2],0.765366865f));
  auto t0=add(f[0],f[4]),t1=sub(f[0],f[4]);
  auto t10=add(t0,t3),t13=sub(t0,t3),t11=add(t1,t2),t12=sub(t1,t2);
  t0=f[7];t1=f[5];t2=f[3];t3=f[1];
  z1=add(t0,t3);auto z2=add(t1,t2),z3=add(t0,t2),z4=add(t1,t3);
  auto z5=mul(add(z3,z4),1.175875602f);
  t0=mul(t0,0.298631336f);t1=mul(t1,2.053119869f);t2=mul(t2,3.072711026f);t3=mul(t3,1.501321110f);
  z1=mul(z1,-0.899976223f);z2=mul(z2,-2.562915447f);z3=add(mul(z3,-1.961570560f),z5);z4=add(mul(z4,-0.390180644f),z5);
  t0=add(t0,add(z1,z3));t1=add(t1,add(z2,z4));t2=add(t2,add(z2,z3));t3=add(t3,add(z1,z4));
  __m256 samples[8]={add(t10,t3),add(t11,t2),add(t12,t1),add(t13,t0),sub(t13,t0),sub(t12,t1),sub(t11,t2),sub(t10,t3)};
  __m256 integers[8];
  for(int x=0;x<8;x++) {
    auto value=_mm256_fmadd_ps(samples[x],_mm256_set1_ps(0.125f),_mm256_set1_ps(128.5f));
    value=_mm256_max_ps(_mm256_setzero_ps(),_mm256_min_ps(value,_mm256_set1_ps(255.0f)));
    integers[x]=_mm256_castsi256_ps(_mm256_cvttps_epi32(value));
  }
  __m256 left[4],right[4];
  transpose4(integers[0],integers[1],integers[2],integers[3],left);
  transpose4(integers[4],integers[5],integers[6],integers[7],right);
  for(int y=0;y<4;y++) {
    auto words=_mm256_packs_epi32(_mm256_castps_si256(left[y]),_mm256_castps_si256(right[y]));
    auto bytes=_mm256_packus_epi16(words,words);
    auto row=_mm_unpacklo_epi8(_mm256_castsi256_si128(bytes),_mm256_extracti128_si256(bytes,1));
    _mm_storeu_si128((__m128i *)(uv+y*pitch),row);
  }
}
extern "C" void mjpeg_chroma_reduced_test(const JCOEF *cb,const JCOEF *cr,unsigned char *uv,int pitch) {
  reduced(cb,cr,uv,pitch);
}

extern "C" int mjpeg_fusion_mcu(j_decompress_ptr c,JBLOCKROW *blocks,JSAMPIMAGE output,JDIMENSION col) {
  if(ctx.c!=c)return 0;
  auto idct=c->idct->inverse_DCT[0];
  idct(c,&c->comp_info[0],*blocks[0],output[0],col*16);
  idct(c,&c->comp_info[0],*blocks[1],output[0],col*16+8);
  auto *dst=ctx.uv+c->input_iMCU_row*4*ctx.pitch+col*16;
  if(ctx.mode==1)mjpeg_chroma_exact(c->comp_info[1].dct_table,c->comp_info[2].dct_table,*blocks[2],*blocks[3],dst,ctx.pitch);
  else reduced(*blocks[2],*blocks[3],dst,ctx.pitch);
  return 1;
}
