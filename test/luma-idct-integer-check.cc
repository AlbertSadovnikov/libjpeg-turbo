#include <array>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <random>
#include <immintrin.h>
#include <cmath>
#include <cstdlib>
#include <vector>
#include "jpeglib.h"

using Block=std::array<JCOEF,64>;
#include "luma-idct-integer.h"
#include "luma-idct-rotation.h"
#include "luma-idct-lifting.h"
#include "luma-idct-sparse.h"
#include "luma-idct-low4.h"
#include "luma-idct-arithmetic.h"
#ifndef TEST_LIFTING
#define TEST_LIFTING 0
#endif
#ifndef TEST_ROTATION
#define TEST_ROTATION 0
#endif
#if defined(TEST_ARITHMETIC)
template<int Mode> struct ArithmeticTestGuard:ArithmeticGuard {
  explicit ArithmeticTestGuard(const short *q):ArithmeticGuard(q,Mode){}
};
#define integer_candidate arithmetic_single<TEST_ARITHMETIC>
#define integer_candidate2 arithmetic_pair<TEST_ARITHMETIC>
#define integer_wide arithmetic_wide<TEST_ARITHMETIC>
#define integer_weights arithmetic_weights[TEST_ARITHMETIC]
#define IntegerGuard ArithmeticTestGuard<TEST_ARITHMETIC>
#define integer_admit arithmetic_admit<TEST_ARITHMETIC>
#define integer_safe2 arithmetic_safe2<TEST_ARITHMETIC>
#elif TEST_LIFTING
#define integer_candidate lifting_candidate
#define integer_candidate2 lifting_candidate2
#define integer_wide lifting_wide
#define integer_weights lifting_weights
#define IntegerGuard LiftingGuard
#define integer_admit lifting_admit
#define integer_safe2 lifting_safe2
#elif TEST_ROTATION
#define integer_candidate rotation_candidate
#define integer_candidate2 rotation_candidate2
#define integer_wide rotation_wide
#define integer_weights rotation_weights
#define IntegerGuard RotationGuard
#define integer_admit rotation_admit
#define integer_safe2 rotation_safe2
#endif
#ifdef TEST_ARITHMETIC
constexpr int test_error_budget=arithmetic_errors[TEST_ARITHMETIC];
#else
constexpr int test_error_budget=TEST_LIFTING?110:TEST_ROTATION?113:93;
#endif
static void synthetic(){
  std::mt19937 rng(12345);
  for(int trial=0;trial<10000;trial++){
    Block b[2]{};short q[64];
    for(int k=0;k<64;k++){
      q[k]=1+rng()%32;
      #ifdef TEST_ARITHMETIC
      for(int j=0;j<2;j++)b[j][k]=int(rng()%9)-4;
#else
      for(int j=0;j<2;j++)b[j][k]=int(rng()%17)-8;
#endif
    }
    if(trial<4){
      for(auto &block:b)block.fill(0);
      q[0]=16;b[0][0]=(trial&1)?1023:-1024;b[1][0]=(trial&2)?1023:-1024;
    }
    unsigned char pair[128],single[64],wide[64];
    integer_candidate2(b,q,pair);
    for(int j=0;j<2;j++){
      integer_candidate(&b[j],q,single);integer_wide(&b[j],q,wide);
      if(memcmp(pair+64*j,single,64)||memcmp(single,wide,64)){
        fprintf(stderr,"Mismatch at trial %d block %d\n",trial,j);std::exit(1);
      }
    }
  }
  puts("20,000 bounded synthetic blocks: single and pair agree with wide oracle");
}

struct ArithmeticAudit:ArithmeticWide {
  inline static unsigned long long wraps=0;
  static long long add(long long a,long long b){auto v=a+b;wraps+=v<-32768||v>32767;return v;}
  static long long sub(long long a,long long b){auto v=a-b;wraps+=v<-32768||v>32767;return v;}
  static long long frac(long long a,int c){
    if(a<-32768||a>32767){fprintf(stderr,"admitted nonlinear input out of range\n");std::exit(1);}
    return ArithmeticWide::frac(a,c);
  }
};
static void audit_modular(const Block &b,const short *q){
  long long x[64];for(int k=0;k<64;k++)x[k]=static_cast<long long>(b[k])*q[k];
  for(int pass=0;pass<2;pass++)for(int j=0;j<8;j++){
    long long v[8];for(int k=0;k<8;k++)v[k]=x[pass?j*8+k:k*8+j];
    arithmetic_transform<5,ArithmeticAudit>(v);
    for(int k=0;k<8;k++)x[pass?j*8+k:k*8+j]=v[k];
  }
  for(auto v:x)if(v+(1<<(INTEGER_PASS_BITS+2))<-32768 || v+(1<<(INTEGER_PASS_BITS+2))>32767){
    fprintf(stderr,"admitted final rounding input out of range\n");std::exit(1);
  }
}
static size_t checked=0, rejected=0;
static void check_pair(const Block *b,const short *q){
  RotationGuard dc_guard(q);unsigned char dc_out[128],dc_wide[64],low4_out[128],low4_pairs[128];
  rotation_low4_safe2<true>(b,q,dc_guard,low4_out);
  rotation_low4_safe2<false>(b,q,dc_guard,low4_pairs);
  rotation_dc_safe2(b,q,dc_guard,dc_out);
  for(int j=0;j<2;j++){
    bool scalar_dc=true;for(int k=1;k<64;k++)scalar_dc&=b[j][k]==0;
    if(rotation_dc_only(b[j])!=scalar_dc){fprintf(stderr,"DC classifier mismatch\n");std::exit(1);}
    bool scalar_low4=true;
    for(int k=0;k<64;k++)if(k/8>=4 || k%8>=4)scalar_low4&=b[j][k]==0;
    if(rotation_low4_only(b[j])!=scalar_low4){fprintf(stderr,"low4 classifier mismatch\n");std::exit(1);}
    rotation_wide(b+j,q,dc_wide);
    if(memcmp(low4_out+64*j,dc_wide,64)||memcmp(low4_pairs+64*j,dc_wide,64)){
      fprintf(stderr,"low4 shortcut mismatch\n");std::exit(1);
    }
    if(memcmp(dc_out+64*j,dc_wide,64)){fprintf(stderr,"DC shortcut mismatch\n");std::exit(1);}
  }
  IntegerGuard guard(q);unsigned char actual[128],wide[64];
  integer_safe2(b,q,guard,actual);
  for(int j=0;j<2;j++){
    integer_wide(b+j,q,wide);
#if defined(TEST_ARITHMETIC) && TEST_ARITHMETIC==5
    unsigned char original[64];rotation_wide(b+j,q,original);
    if(memcmp(wide,original,64)){fprintf(stderr,"modular wide changed output\n");std::exit(1);}
#endif
    long long bound=0;bool expected=guard.usable;
    for(int k=0;k<64;k++){
      if(b[j][k]==-32768)expected=false;
      bound+=std::abs(int(b[j][k]))*static_cast<long long>(q[k])*integer_weights[k];
    }
    expected=expected && bound<=32767-test_error_budget-(1<<(INTEGER_PASS_BITS+2));
    if(integer_admit(b+j,guard)!=expected){fprintf(stderr,"Admission arithmetic mismatch\n");std::exit(1);}
    if(memcmp(actual+64*j,wide,64)){fprintf(stderr,"Safe mismatch at block %zu\n",checked);std::exit(1);}
    if(integer_admit(b+j,guard)){
#if defined(TEST_ARITHMETIC) && TEST_ARITHMETIC==5
      audit_modular(b[j],q);
#endif
      unsigned char narrow[64];integer_candidate(b+j,q,narrow);
      if(memcmp(narrow,wide,64)){fprintf(stderr,"Invalid admission at block %zu\n",checked);std::exit(1);}
    }else rejected++;
    checked++;
  }
}
static void encoded(){
  std::mt19937 rng(24680);
  const double scales[]={1,1.387039845,1.306562965,1.175875602,1,.785694958,.541196100,.275899379};
  const int levels[]={1,2,5,17,63,127,255,0};
  bool quadrant_exercised=false;
  for(int pattern=0;pattern<320;pattern++)for(int level:levels){
    unsigned char pixels[64];
    for(int y=0;y<8;y++)for(int x=0;x<8;x++){
      if(pattern==0)pixels[8*y+x]=((y<4)==(x<4))?255:0;
      else if(pattern<=64){
        int u=(pattern-1)/8,v=(pattern-1)%8;
        pixels[8*y+x]=std::cos((2*y+1)*u*std::acos(-1.)/16)*std::cos((2*x+1)*v*std::acos(-1.)/16)>=0?255:0;
      }else if(pattern==65)pixels[8*y+x]=0;
      else if(pattern==66)pixels[8*y+x]=255;
      else if(pattern<192)pixels[8*y+x]=(rng()&1)?255:0;
      else pixels[8*y+x]=rng()%256;
    }
    jpeg_compress_struct c{};jpeg_error_mgr e{};c.err=jpeg_std_error(&e);jpeg_create_compress(&c);
    unsigned char *data=nullptr;unsigned long length=0;jpeg_mem_dest(&c,&data,&length);
    c.image_width=8;c.image_height=8;c.input_components=1;c.in_color_space=JCS_GRAYSCALE;
    jpeg_set_defaults(&c);unsigned int table[64];for(auto &v:table)v=level?level:1+rng()%255;
    jpeg_add_quant_table(&c,0,table,100,TRUE);c.dct_method=JDCT_ISLOW;
    jpeg_start_compress(&c,TRUE);
    while(c.next_scanline<8){JSAMPROW row=pixels+8*c.next_scanline;jpeg_write_scanlines(&c,&row,1);}
    jpeg_finish_compress(&c);jpeg_destroy_compress(&c);
    jpeg_decompress_struct d{};d.err=jpeg_std_error(&e);jpeg_create_decompress(&d);
    jpeg_mem_src(&d,data,length);jpeg_read_header(&d,TRUE);auto arrays=jpeg_read_coefficients(&d);
    auto row=d.mem->access_virt_barray((j_common_ptr)&d,arrays[0],0,1,FALSE);
    Block b[2];memcpy(b[0].data(),row[0][0],sizeof(Block));b[1]=b[0];
    short q[64];
    for(int k=0;k<64;k++){
#ifdef TEST_ARITHMETIC
      const double *chosen=TEST_ARITHMETIC==5?scales:arithmetic_scales[TEST_ARITHMETIC];
#else
      const double *chosen=scales;
#endif
      q[k]=short(std::lround(table[k]*chosen[k/8]*chosen[k%8]*(1<<INTEGER_PASS_BITS)));
    }
    check_pair(b,q);
    if(pattern==0 && level==1){
      IntegerGuard guard(q);quadrant_exercised=!integer_admit(b,guard);
      unsigned char narrow[64],wide[64];integer_candidate(b,q,narrow);integer_wide(b,q,wide);
      printf("Quadrant Q=1: admission=%s; unchecked mismatches=%d\n",quadrant_exercised?"wide fallback":"narrow",int(memcmp(narrow,wide,64)!=0));
    }
    jpeg_destroy_decompress(&d);std::free(data);
  }
#if !defined(TEST_ARITHMETIC) || TEST_ARITHMETIC!=5
  if(!quadrant_exercised){fprintf(stderr,"Expected quadrant to exercise fallback\n");std::exit(1);}
#endif
  printf("2,560 encoded pixel blocks checked at B=%d\n",INTEGER_PASS_BITS);
}
static void arbitrary(){
  std::mt19937 rng(13579);
  for(int t=0;t<10000;t++){
    Block b[2];short q[64];
    for(int k=0;k<64;k++){
      for(auto &v:b)v[k]=short(int(rng()%65536)-32768);
      q[k]=short(rng()%(t%3==0?4:t%3==1?32:32768));
    }
    if(t==0){for(auto &v:b)v.fill(-32768);for(auto &v:q)v=32767;}
    check_pair(b,q);
  }
  for(int k=0;k<64;k++)for(int delta=-2;delta<=2;delta++){
    Block b[2]{};short q[64];std::fill(q,q+64,1);
    int magnitude=(32767-test_error_budget-(1<<(INTEGER_PASS_BITS+2)))/integer_weights[k]+delta;
    b[0][k]=short(magnitude);b[1][k]=short(-magnitude);
    check_pair(b,q);
  }
}
static void dc_specific(){
  const int extrema[]={-32768,-2044,-1024,-1,0,1,1023,2044,32767};
  const int quantizers[]={-32768,-1,0,1,4,32767};
  size_t cases=0;
  for(int dc:extrema)for(int quant:quantizers){
    Block b[2]{};b[0][0]=short(dc);b[1][0]=short(-dc==32768?32767:-dc);
    short q[64];std::fill(q,q+64,short(quant));
    check_pair(b,q);cases+=2;
    for(int lane=0;lane<2;lane++)for(int k=1;k<64;k++){
      for(int value: {-32768,-1,1,32767}){
        b[lane][k]=short(value);check_pair(b,q);cases+=2;
      }
      b[lane][k]=0;
    }
  }
  printf("%zu DC-specific lane/extreme/AC-position cases checked\n",cases);
}
static void low4_specific(){
  std::mt19937 rng(424242);
  size_t cases=0;
  for(int trial=0;trial<4000;trial++){
    Block b[2]{};short q[64];
    for(auto &v:q)v=short(1+rng()%32);
    int magnitude=trial%2?8:2048;
    for(auto &block:b)for(int r=0;r<4;r++)for(int c=0;c<4;c++)
      block[8*r+c]=short(int(rng()%(2*magnitude))-magnitude);
    check_pair(b,q);cases+=2;
    if(trial<1000){
      for(int lane=0;lane<2;lane++)for(int k=0;k<64;k++)if(k/8>=4 || k%8>=4){
        b[lane][k]=short(trial%2?-32768:1);check_pair(b,q);cases+=2;b[lane][k]=0;
      }
    }
  }
  printf("%zu low4-specific lane/support/boundary cases checked\n",cases);
}
int main(){
#ifdef TEST_ARITHMETIC
  printf("Testing arithmetic variant: %s\n",arithmetic_names[TEST_ARITHMETIC]);
#else
  printf("Testing %s\n",TEST_LIFTING?"lifting":TEST_ROTATION?"rotation":"original");
#endif
  synthetic();encoded();arbitrary();dc_specific();low4_specific();
  printf("Modular intermediate wraps audited: %llu\n",ArithmeticAudit::wraps);
  printf("%zu guarded blocks match wide oracle; %zu used fallback\n",checked,rejected);
}
