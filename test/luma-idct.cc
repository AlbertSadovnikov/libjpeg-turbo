#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <array>
#include <vector>
#include <algorithm>
#include <chrono>
#include <immintrin.h>
#define JPEG_INTERNALS
#include "jpeglib.h"

// Four independent luma blocks per SSE vector. AAN factorization, with
// floating-point dequantization and rounding only at the final pixel store.
using V = float __attribute__((vector_size(16)));
static inline void aan(V *x, int s) {
  V a=x[0], b=x[2*s], c=x[4*s], d=x[6*s];
  V p=a+c, q=a-c, r=b+d, t=(b-d)*1.414213562f-r;
  V e0=p+r,e3=p-r,e1=q+t,e2=q-t;
  V z13=x[5*s]+x[3*s],z10=x[5*s]-x[3*s];
  V z11=x[s]+x[7*s],z12=x[s]-x[7*s];
  V o7=z11+z13, u=(z11-z13)*1.414213562f;
  V z5=(z10+z12)*1.847759065f;
  V o6=z5-z10*2.613125930f-o7;
  V o5=u-o6, o4=z5-z12*1.082392200f-o5;
  x[0]=e0+o7;x[7*s]=e0-o7;x[s]=e1+o6;x[6*s]=e1-o6;
  x[2*s]=e2+o5;x[5*s]=e2-o5;x[3*s]=e3+o4;x[4*s]=e3-o4;
}
using Block=std::array<JCOEF,64>;
__attribute__((noinline)) static void candidate(const Block *b,const float *q,unsigned char *out) {
  V w[64];
  for(int k=0;k<64;k+=4){
    __m128 v[4];
    for(int j=0;j<4;j++){
      __m128i a=_mm_loadl_epi64((const __m128i*)(b[j].data()+k));
      v[j]=_mm_cvtepi32_ps(_mm_unpacklo_epi16(a,_mm_cmpgt_epi16(_mm_setzero_si128(),a)));
    }
    _MM_TRANSPOSE4_PS(v[0],v[1],v[2],v[3]);
    for(int j=0;j<4;j++)w[k+j]=V(v[j])*q[k+j];
  }
  for(int c=0;c<8;c++)aan(w+c,8);
  for(int r=0;r<8;r++)aan(w+8*r,1);
  for(int k=0;k<64;k+=4){
    __m128 v[4];for(int j=0;j<4;j++)v[j]=w[k+j]+128.5f;
    _MM_TRANSPOSE4_PS(v[0],v[1],v[2],v[3]);
    for(int j=0;j<4;j++){
      __m128i a=_mm_cvttps_epi32(v[j]);a=_mm_packs_epi32(a,a);a=_mm_packus_epi16(a,a);
      int pixels=_mm_cvtsi128_si32(a);memcpy(out+j*64+k,&pixels,4);
    }
  }
}
#include "luma-idct-integer.h"
#include "luma-idct-rotation.h"
#include "luma-idct-lifting.h"
#include "luma-idct-sparse.h"
#include "luma-idct-low4.h"
#include "luma-idct-arithmetic.h"
template<int Mode> static size_t verify_arithmetic(const std::vector<Block> &blocks,const short *q,const ArithmeticGuard &g){
  size_t fallback=0;
  for(size_t i=0;i<blocks.size();i+=2){
    unsigned char pair[128],wide[64];arithmetic_safe2<Mode>(&blocks[i],q,g,pair);
    for(int j=0;j<2;j++){
      arithmetic_wide<Mode>(&blocks[i+j],q,wide);
      if(memcmp(wide,pair+64*j,64)){fprintf(stderr,"arithmetic mode %d mismatch block %zu\n",Mode,i+j);exit(2);}
      fallback+=!arithmetic_admit<Mode>(&blocks[i+j],g);
    }
  }
  return fallback;
}
struct Decoder {
  jpeg_decompress_struct c{};jpeg_error_mgr e{};FILE *f;
  Decoder(const char *path,J_DCT_METHOD method){
    f=fopen(path,"rb");if(!f){perror(path);exit(1);}c.err=jpeg_std_error(&e);
    jpeg_create_decompress(&c);jpeg_stdio_src(&c,f);jpeg_read_header(&c,TRUE);
    c.raw_data_out=TRUE;c.dct_method=method;jpeg_start_decompress(&c);
  }
  ~Decoder(){jpeg_destroy_decompress(&c);fclose(f);}
};
static void stock(Decoder &d,const Block *b,unsigned char *out){
  JSAMPROW rows[8];for(int r=0;r<8;r++)rows[r]=out+8*r;
  d.c.idct->inverse_DCT[0](&d.c,&d.c.comp_info[0],const_cast<JCOEF*>(b->data()),rows,0);
}
int main(int argc,char **argv){
  if(argc<2)return 1;
  for(int file=1;file<argc;file++){
    Decoder slow(argv[file],JDCT_ISLOW),fast(argv[file],JDCT_IFAST),flt(argv[file],JDCT_FLOAT);
    jpeg_decompress_struct c{};jpeg_error_mgr e{};c.err=jpeg_std_error(&e);jpeg_create_decompress(&c);
    FILE *f=fopen(argv[file],"rb");jpeg_stdio_src(&c,f);jpeg_read_header(&c,TRUE);auto ar=jpeg_read_coefficients(&c);
    std::vector<Block> blocks;
    for(unsigned y=0;y<c.comp_info[0].height_in_blocks;y++){
      auto row=c.mem->access_virt_barray((j_common_ptr)&c,ar[0],y,1,FALSE);
      for(unsigned x=0;x<c.comp_info[0].width_in_blocks;x++){
        Block b;memcpy(b.data(),row[0][x],sizeof(b));blocks.push_back(b);
      }
    }
    size_t actual=blocks.size();while(blocks.size()%4)blocks.push_back(blocks.back());
    short iq[64];float q[64];const double s[]={1,1.387039845,1.306562965,1.175875602,1,.785694958,.541196100,.275899379};
    auto qt=c.quant_tbl_ptrs[c.comp_info[0].quant_tbl_no];
    for(int k=0;k<64;k++)q[k]=float(qt->quantval[k]*s[k/8]*s[k%8]/8);
    for(int k=0;k<64;k++){
      long value=std::lround(q[k]*(8 << INTEGER_PASS_BITS));
      if(value<0 || value>32767){fprintf(stderr,"scaled quantizer out of supported range\n");return 2;}
      iq[k]=short(value);
    }
    bool compensate=std::getenv("IDCT_UNCOMPENSATED")==nullptr;
    short aq[8][64];std::vector<ArithmeticGuard> arithmetic_guards;
    for(int mode=0;mode<8;mode++){
      for(int k=0;k<64;k++){
        long value=std::lround(qt->quantval[k]*(compensate?arithmetic_scales[mode][k/8]:s[k/8])*(compensate?arithmetic_scales[mode][k%8]:s[k%8])*(1<<INTEGER_PASS_BITS));
        if(value<0||value>32767){fprintf(stderr,"arithmetic table out of range\n");return 2;}
        aq[mode][k]=short(value);
      }
      if(mode==5)memcpy(aq[mode],iq,sizeof(iq)); // Bit-exact modular control.
      arithmetic_guards.emplace_back(aq[mode],mode);
    }
    size_t arithmetic_fallbacks[8]={verify_arithmetic<0>(blocks,aq[0],arithmetic_guards[0]),verify_arithmetic<1>(blocks,aq[1],arithmetic_guards[1]),verify_arithmetic<2>(blocks,aq[2],arithmetic_guards[2]),verify_arithmetic<3>(blocks,aq[3],arithmetic_guards[3]),verify_arithmetic<4>(blocks,aq[4],arithmetic_guards[4]),verify_arithmetic<5>(blocks,aq[5],arithmetic_guards[5]),verify_arithmetic<6>(blocks,aq[6],arithmetic_guards[6]),verify_arithmetic<7>(blocks,aq[7],arithmetic_guards[7])};
    IntegerGuard guard(iq);RotationGuard rotation_guard(iq);LiftingGuard lifting_guard(iq);
    std::vector<unsigned char> ref(blocks.size()*64),out(ref.size());
    for(size_t i=0;i<blocks.size();i++)stock(slow,&blocks[i],ref.data()+64*i);
    // Output comparison is outside timing; the algebraic guard supplies the proof.
    for(size_t i=0;i<blocks.size();i+=2){
      unsigned char pair[128],wide[64];integer_safe2(&blocks[i],iq,guard,pair);
      for(int j=0;j<2;j++){
        integer_wide(&blocks[i+j],iq,wide);
        if(memcmp(wide,pair+64*j,64)){fprintf(stderr,"safe kernel disagrees with oracle: %s block %zu\n",argv[file],i+j);return 2;}
      }
    }
    for(size_t i=0;i<blocks.size();i+=2){
      unsigned char pair[128],wide[64];rotation_safe2(&blocks[i],iq,rotation_guard,pair);
      for(int j=0;j<2;j++){
        rotation_wide(&blocks[i+j],iq,wide);
        if(memcmp(wide,pair+64*j,64)){fprintf(stderr,"rotation disagrees with oracle\n");return 2;}
      }
    }
    for(size_t i=0;i<blocks.size();i+=2){
      unsigned char pair[128],wide[64];lifting_safe2(&blocks[i],iq,lifting_guard,pair);
      for(int j=0;j<2;j++){
        lifting_wide(&blocks[i+j],iq,wide);
        if(memcmp(wide,pair+64*j,64)){fprintf(stderr,"lifting disagrees with oracle\n");return 2;}
      }
    }
    size_t dc_blocks=0,dc_pairs=0,dc_mixed=0,low2=0,low4=0,zero_columns=0,zero_rows=0;
    for(size_t i=0;i<blocks.size();i+=2){
      bool a=rotation_dc_only(blocks[i]),b=rotation_dc_only(blocks[i+1]);
      dc_blocks+=a+b;dc_pairs+=a&&b;dc_mixed+=a!=b;
      unsigned char pair[128],wide[64];rotation_dc_safe2(&blocks[i],iq,rotation_guard,pair);
      for(int j=0;j<2;j++){
        rotation_wide(&blocks[i+j],iq,wide);
        if(memcmp(wide,pair+64*j,64)){fprintf(stderr,"DC shortcut disagrees with oracle\n");return 2;}
        bool small2=true,small4=true;
        for(int k=0;k<64;k++)if(blocks[i+j][k]){
          if(k/8>=2 || k%8>=2)small2=false;
          if(k/8>=4 || k%8>=4)small4=false;
        }
        low2+=small2;low4+=small4;
        for(int c=0;c<8;c++){
          bool zero=true;for(int r=1;r<8;r++)zero&=blocks[i+j][8*r+c]==0;
          zero_columns+=zero;
        }
        bool zero=true;for(int k=8;k<64;k++)zero&=blocks[i+j][k]==0;
        zero_rows+=zero;
      }
    }
    fprintf(stderr,"sparse blocks=%zu DC=%zu DCpairs=%zu mixed=%zu low2=%zu low4=%zu zeroColumns=%zu firstRowOnly=%zu\n",blocks.size(),dc_blocks,dc_pairs,dc_mixed,low2,low4,zero_columns,zero_rows);
    size_t low4_pairs=0,low4_mixed=0;
    for(size_t i=0;i<blocks.size();i+=2){
      bool a=rotation_low4_only(blocks[i]),b=rotation_low4_only(blocks[i+1]);
      low4_pairs+=a&&b;low4_mixed+=a!=b;
      unsigned char pair[128],wide[64],pair_only[128];
      rotation_low4_safe2<true>(&blocks[i],iq,rotation_guard,pair);
      rotation_low4_safe2<false>(&blocks[i],iq,rotation_guard,pair_only);
      for(int j=0;j<2;j++){
        rotation_wide(&blocks[i+j],iq,wide);
        if(memcmp(wide,pair+64*j,64)||memcmp(wide,pair_only+64*j,64)){
          fprintf(stderr,"low4 shortcut disagrees with oracle\n");return 2;
        }
      }
    }
    size_t lifting_fallback=0;for(const auto &b:blocks)lifting_fallback+=!lifting_admit(&b,lifting_guard);
    size_t rotation_fallback=0;for(const auto &b:blocks)rotation_fallback+=!rotation_admit(&b,rotation_guard);
    fprintf(stderr,"rotation fallback %zu/%zu\n",rotation_fallback,blocks.size());
    size_t fallback=0;for(const auto &b:blocks)fallback+=!integer_admit(&b,guard);
    fprintf(stderr,"%s: fallback %zu/%zu\n",argv[file],fallback,blocks.size());
    bool reverse_order=std::getenv("IDCT_REVERSE_ORDER")!=nullptr;
    printf("{\"file\":\"%s\",\"blocks\":%zu,\"pass_bits\":%d,\"fallback_blocks\":%zu,\"rotation_fallback_blocks\":%zu,\"lifting_fallback_blocks\":%zu,\"reverse_order\":%s,\"dc_blocks\":%zu,\"dc_pairs\":%zu,\"dc_mixed_pairs\":%zu,\"low2_blocks\":%zu,\"low4_blocks\":%zu,\"zero_ac_columns\":%zu,\"first_row_only_blocks\":%zu,\"low4_pairs\":%zu,\"low4_mixed_pairs\":%zu,\"arithmetic_compensated\":%s,\"arithmetic_fallback_blocks\":[",argv[file],actual,INTEGER_PASS_BITS,fallback,rotation_fallback,lifting_fallback,reverse_order?"true":"false",dc_blocks,dc_pairs,dc_mixed,low2,low4,zero_columns,zero_rows,low4_pairs,low4_mixed,compensate?"true":"false");
    for(int mode=0;mode<8;mode++)printf("%s%zu",mode?",":"",arithmetic_fallbacks[mode]);
    printf("],\"kernels\":[");
    for(int slot=0;slot<22;slot++){
      int kind=reverse_order?21-slot:slot;
      auto run=[&](){if(kind==21){for(size_t j=0;j<blocks.size();j+=2)arithmetic_safe2<7>(&blocks[j],aq[7],arithmetic_guards[7],out.data()+64*j);}else if(kind==20){for(size_t j=0;j<blocks.size();j+=2)arithmetic_safe2<6>(&blocks[j],aq[6],arithmetic_guards[6],out.data()+64*j);}else if(kind==19){for(size_t j=0;j<blocks.size();j+=2)arithmetic_safe2<5>(&blocks[j],aq[5],arithmetic_guards[5],out.data()+64*j);}else if(kind==18){for(size_t j=0;j<blocks.size();j+=2)arithmetic_safe2<4>(&blocks[j],aq[4],arithmetic_guards[4],out.data()+64*j);}else if(kind==17){for(size_t j=0;j<blocks.size();j+=2)arithmetic_safe2<3>(&blocks[j],aq[3],arithmetic_guards[3],out.data()+64*j);}else if(kind==16){for(size_t j=0;j<blocks.size();j+=2)arithmetic_safe2<2>(&blocks[j],aq[2],arithmetic_guards[2],out.data()+64*j);}else if(kind==15){for(size_t j=0;j<blocks.size();j+=2)arithmetic_safe2<1>(&blocks[j],aq[1],arithmetic_guards[1],out.data()+64*j);}else if(kind==14){for(size_t j=0;j<blocks.size();j+=2)arithmetic_safe2<0>(&blocks[j],aq[0],arithmetic_guards[0],out.data()+64*j);}else if(kind==13){for(size_t i=0;i<blocks.size();i+=2)rotation_low4_safe2<true>(&blocks[i],iq,rotation_guard,out.data()+64*i);}else if(kind==12){for(size_t i=0;i<blocks.size();i+=2)rotation_low4_safe2<false>(&blocks[i],iq,rotation_guard,out.data()+64*i);}else if(kind==11){for(size_t i=0;i<blocks.size();i+=2)rotation_dc_safe2(&blocks[i],iq,rotation_guard,out.data()+64*i);}else if(kind==10){for(size_t i=0;i<blocks.size();i+=2)lifting_safe2(&blocks[i],iq,lifting_guard,out.data()+64*i);}else if(kind==9){for(size_t i=0;i<blocks.size();i+=2)lifting_candidate2(&blocks[i],iq,out.data()+64*i);}else if(kind==8){for(size_t i=0;i<blocks.size();i+=2)rotation_safe2(&blocks[i],iq,rotation_guard,out.data()+64*i);}else if(kind==7){for(size_t i=0;i<blocks.size();i+=2)rotation_candidate2(&blocks[i],iq,out.data()+64*i);}else if(kind==6){for(size_t i=0;i<blocks.size();i+=2)integer_safe2(&blocks[i],iq,guard,out.data()+64*i);}else if(kind==5){for(size_t i=0;i<blocks.size();i+=2)integer_candidate2(&blocks[i],iq,out.data()+64*i);}else if(kind==4){for(size_t i=0;i<blocks.size();i++)integer_candidate(&blocks[i],iq,out.data()+64*i);}else if(kind==3){for(size_t i=0;i<blocks.size();i+=4)candidate(&blocks[i],q,out.data()+64*i);}else{
        Decoder &d=kind==0?slow:kind==1?fast:flt;
        for(size_t i=0;i<blocks.size();i++)stock(d,&blocks[i],out.data()+64*i);
      }};
      run();double sq=0,abs=0;int peak=0;size_t different=0;
      for(size_t i=0;i<actual*64;i++){int err=int(out[i])-ref[i];sq+=err*err;abs+=std::abs(err);peak=std::max(peak,std::abs(err));different+=err!=0;}
      std::vector<double> times;unsigned long long checksum=0;
      int passes=std::max(8,int(200000/blocks.size()));
      for(int trial=0;trial<7;trial++){
        auto begin=std::chrono::steady_clock::now();
        for(int p=0;p<passes;p++){run();asm volatile("" : : "r"(out.data()) : "memory");}
        times.push_back(std::chrono::duration<double,std::nano>(std::chrono::steady_clock::now()-begin).count()/(passes*blocks.size()));
        for(auto v:out)checksum+=v;
      }
      std::sort(times.begin(),times.end());
      printf("%s{\"name\":\"%s\",\"ns_per_block\":%.3f,\"mae\":%.5f,\"rmse\":%.5f,\"max_error\":%d,\"different_fraction\":%.5f,\"checksum\":%llu,\"trials_ns\":[",slot?",":"",(const char*[]){"islow","ifast","float","aan-float4","aan-q15","aan-q15-pair","aan-q15-safe","rotation-q15-pair","rotation-q15-safe","lifting-q15-pair","lifting-q15-safe","rotation-dc-safe","rotation-low4-pairs-safe","rotation-low4-mixed-safe",arithmetic_names[0],arithmetic_names[1],arithmetic_names[2],arithmetic_names[3],arithmetic_names[4],arithmetic_names[5],arithmetic_names[6],arithmetic_names[7]}[kind],times[3],abs/(actual*64),sqrt(sq/(actual*64)),peak,double(different)/(actual*64),checksum);
      for(size_t t=0;t<times.size();t++)printf("%s%.3f",t?",":"",times[t]);printf("]}");
    }
    puts("]}");jpeg_destroy_decompress(&c);fclose(f);
  }
}
