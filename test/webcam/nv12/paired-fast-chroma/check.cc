#include <cstdio>
#include <cstdlib>
#include <cstddef>
#define JPEG_INTERNALS
#include "jpeglib.h"
#include "embedded_frame.h"
#include <vector>
#include <array>
#include <cstring>
#include <cstdint>
#include <chrono>
extern "C" void mjpeg_chroma_fast_pair(const void*,const void*,const JCOEF*,const JCOEF*,unsigned char*,int);
extern "C" void jsimd_idct_ifast_sse2(const void*,const JCOEF*,JSAMPARRAY,unsigned);
extern "C" int mjpeg_fusion_mcu(j_decompress_ptr,JBLOCKROW*,JSAMPIMAGE,JDIMENSION){return 0;}
int main(){
 jpeg_decompress_struct c{},d{};jpeg_error_mgr e{},f{};c.err=jpeg_std_error(&e);d.err=jpeg_std_error(&f);
 jpeg_create_decompress(&c);jpeg_mem_src(&c,mjpeg_bench::kJpeg,mjpeg_bench::kJpegSize);jpeg_read_header(&c,TRUE);c.raw_data_out=TRUE;c.dct_method=JDCT_IFAST;jpeg_start_decompress(&c);
 jpeg_create_decompress(&d);jpeg_mem_src(&d,mjpeg_bench::kJpeg,mjpeg_bench::kJpegSize);jpeg_read_header(&d,TRUE);auto arrays=jpeg_read_coefficients(&d);
 std::vector<std::array<JCOEF,128>> pairs;
 for(unsigned y=0;y<d.comp_info[1].height_in_blocks;y++){
  auto a=d.mem->access_virt_barray((j_common_ptr)&d,arrays[1],y,1,FALSE),b=d.mem->access_virt_barray((j_common_ptr)&d,arrays[2],y,1,FALSE);
  for(unsigned x=0;x<d.comp_info[1].width_in_blocks;x++){std::array<JCOEF,128>v;std::memcpy(v.data(),a[0][x],128);std::memcpy(v.data()+64,b[0][x],128);pairs.push_back(v);}
 }
 unsigned char cb[8][29],cr[8][29],expected[4][29],out[4][29];JSAMPROW a[8],b[8];for(int y=0;y<8;y++){a[y]=cb[y];b[y]=cr[y];}
 const void *q0=c.comp_info[1].dct_table,*q1=c.comp_info[2].dct_table;
 auto native=[&](const JCOEF*v){
  jsimd_idct_ifast_sse2(q0,v,a,3);jsimd_idct_ifast_sse2(q1,v+64,b,3);
  for(int y=0;y<4;y++)for(int x=0;x<8;x++){expected[y][3+2*x]=(unsigned(cb[2*y][3+x])+cb[2*y+1][3+x]+1)/2;expected[y][4+2*x]=(unsigned(cr[2*y][3+x])+cr[2*y+1][3+x]+1)/2;}
 };
 auto check=[&](const JCOEF*v){std::memset(expected,0xa5,sizeof(expected));std::memset(out,0xa5,sizeof(out));native(v);mjpeg_chroma_fast_pair(q0,q1,v,v+64,&out[0][3],29);if(std::memcmp(expected,out,sizeof(out))){std::fprintf(stderr,"Fast chroma mismatch\n");std::exit(1);}};
 for(auto &v:pairs)check(v.data());
 uint32_t state=123456789;auto next=[&](){state^=state<<13;state^=state>>17;state^=state<<5;return state;};
 alignas(32) JCOEF coeff[128];alignas(32) int16_t quant0[64],quant1[64];
 for(int t=0;t<10000;t++){
  for(int k=0;k<128;k++)coeff[k]=t%5==0?(k%64?0:int(next()%2049)-1024):t%5==1?(k%64<8?int(next()%129)-64:0):int(next()%65536)-32768;
  for(int k=0;k<64;k++){quant0[k]=int(next()%65536)-32768;quant1[k]=t%3==0?quant0[k]:int(next()%65536)-32768;}
  q0=quant0;q1=quant1;check(coeff);
  quant1[t%64]^=1;check(coeff); // Same pointers, changed independent table.
 }
 q0=c.comp_info[1].dct_table;q1=c.comp_info[2].dct_table;
 std::printf("{\"captured_chroma_pairs\":%zu,\"synthetic_pairs\":10000,\"extra_inplace_table_mutations\":10000,\"padding_checked\":true,\"timings\":[",pairs.size());
 for(int r=0;r<5;r++)for(int k=0;k<2;k++){
  auto start=std::chrono::steady_clock::now();for(int pass=0;pass<50;pass++)for(auto&v:pairs){if(k)mjpeg_chroma_fast_pair(q0,q1,v.data(),v.data()+64,&out[0][3],29);else native(v.data());}
  auto ns=std::chrono::duration<double,std::nano>(std::chrono::steady_clock::now()-start).count()/(50*pairs.size());
  std::printf("%s{\"round\":%d,\"paired\":%d,\"ns_pair\":%.6f}",r||k?",":"",r,k,ns);
 }
 std::puts("]}");jpeg_destroy_decompress(&c);jpeg_destroy_decompress(&d);
}
