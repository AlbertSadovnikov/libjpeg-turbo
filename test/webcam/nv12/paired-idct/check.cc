#include <cstdlib>
#include <cstdio>
#include <cstddef>
#define JPEG_INTERNALS
#include "jpeglib.h"
#include "embedded_frame.h"
#include <cstring>
#include <cstdint>
#include <chrono>
#include <vector>
#include <array>
extern "C" void mjpeg_idct_ifast_pair(const void*,const JCOEF*,const JCOEF*,JSAMPARRAY,unsigned);
extern "C" void jsimd_idct_ifast_sse2(const void*,const JCOEF*,JSAMPARRAY,unsigned);
int main(){
 jpeg_decompress_struct c{},d{};jpeg_error_mgr e{},f{};
 c.err=jpeg_std_error(&e);jpeg_create_decompress(&c);jpeg_mem_src(&c,mjpeg_bench::kJpeg,mjpeg_bench::kJpegSize);jpeg_read_header(&c,TRUE);c.raw_data_out=TRUE;c.dct_method=JDCT_IFAST;jpeg_start_decompress(&c);
 d.err=jpeg_std_error(&f);jpeg_create_decompress(&d);jpeg_mem_src(&d,mjpeg_bench::kJpeg,mjpeg_bench::kJpegSize);jpeg_read_header(&d,TRUE);auto arrays=jpeg_read_coefficients(&d);
 std::vector<std::array<JCOEF,128>> pairs;
 unsigned both_sparse=0,one_sparse=0;
 for(unsigned y=0;y<d.comp_info[0].height_in_blocks;y++){
  auto row=(*d.mem->access_virt_barray)((j_common_ptr)&d,arrays[0],y,1,FALSE);
  for(unsigned x=0;x+1<d.comp_info[0].width_in_blocks;x+=2){
   std::array<JCOEF,128> b;std::memcpy(b.data(),row[0][x],128);std::memcpy(b.data()+64,row[0][x+1],128);pairs.push_back(b);
   bool a=true,z=true;for(int k=8;k<64;k++){a&=b[k]==0;z&=b[64+k]==0;}both_sparse+=a&&z;one_sparse+=a!=z;
  }
 }
 unsigned char ref[8][29],out[8][29];JSAMPROW rr[8],oo[8];for(int y=0;y<8;y++){rr[y]=ref[y];oo[y]=out[y];}
 auto q=c.comp_info[0].dct_table;
 auto check=[&](const JCOEF *b){
  std::memset(ref,0xa5,sizeof(ref));std::memset(out,0xa5,sizeof(out));
  jsimd_idct_ifast_sse2(q,const_cast<JCOEF*>(b),rr,3);jsimd_idct_ifast_sse2(q,const_cast<JCOEF*>(b+64),rr,11);
  mjpeg_idct_ifast_pair(q,b,b+64,oo,3);
  if(std::memcmp(ref,out,sizeof(out))){std::fprintf(stderr,"Kernel mismatch\n");std::exit(1);}
 };
 for(auto &b:pairs)check(b.data());
 uint32_t rng=123456789;auto next=[&](){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;};
 alignas(32) JCOEF b[128];
 for(int t=0;t<10000;t++){
  for(int k=0;k<128;k++)b[k]=t%5==0?(k%64==0?int(next()%2049)-1024:0):t%5==1?(k%64<8?int(next()%129)-64:0):int(next()%65536)-32768;
  check(b);
 }
 std::printf("{\"capture_pairs\":%zu,\"both_sparse\":%u,\"one_sparse\":%u,\"random_pairs\":10000,\"timings\":[",pairs.size(),both_sparse,one_sparse);
 for(int trial=0;trial<5;trial++)for(int kind=0;kind<2;kind++){
  auto start=std::chrono::steady_clock::now();
  for(int pass=0;pass<50;pass++)for(auto &v:pairs){if(kind)mjpeg_idct_ifast_pair(q,v.data(),v.data()+64,oo,3);else{jsimd_idct_ifast_sse2(q,v.data(),oo,3);jsimd_idct_ifast_sse2(q,v.data()+64,oo,11);}}
  double ns=std::chrono::duration<double,std::nano>(std::chrono::steady_clock::now()-start).count()/(50*pairs.size());
  std::printf("%s{\"trial\":%d,\"paired\":%d,\"ns_per_pair\":%.4f}",trial||kind?",":"",trial,kind,ns);
 }
 std::puts("]}");jpeg_destroy_decompress(&c);jpeg_destroy_decompress(&d);
}
