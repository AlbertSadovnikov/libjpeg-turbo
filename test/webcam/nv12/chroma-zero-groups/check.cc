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
extern "C" int ref_mjpeg_fusion_begin(j_decompress_ptr,unsigned char*,int,int);
extern "C" int zero_mjpeg_fusion_begin(j_decompress_ptr,unsigned char*,int,int);
extern "C" void ref_mjpeg_chroma_reduced_test(const JCOEF*,const JCOEF*,unsigned char*,int);
extern "C" void zero_mjpeg_chroma_reduced_test(const JCOEF*,const JCOEF*,unsigned char*,int);
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
 unsigned char scratch[4][1920],a[4][29],b[4][29];
 auto setup=[&]{if(!ref_mjpeg_fusion_begin(&c,&scratch[0][0],1920,2)||!zero_mjpeg_fusion_begin(&c,&scratch[0][0],1920,2))std::abort();};
 auto check=[&](const JCOEF*v){std::memset(a,0xa5,sizeof(a));std::memset(b,0xa5,sizeof(b));ref_mjpeg_chroma_reduced_test(v,v+64,&a[0][3],29);zero_mjpeg_chroma_reduced_test(v,v+64,&b[0][3],29);if(std::memcmp(a,b,sizeof(a))){std::fprintf(stderr,"Zero-group mismatch\n");std::exit(1);}};
 setup();for(auto&v:pairs)check(v.data());
 uint32_t state=123456789;auto next=[&](){state^=state<<13;state^=state>>17;state^=state<<5;return state;};
 alignas(32) JCOEF v[128];
 for(int t=0;t<20000;t++){
  for(int k=0;k<128;k++){
   int row=(k%64)/8;
   v[k]=t%5==0?(k%64?0:int(next()%2049)-1024):t%5==1?(row==0?int(next()%129)-64:0):t%5==2?(row<=3?(t>=10000?int(next()%33)-16:int(next()%65536)-32768):0):t%5==3?(t>=10000?int(next()%33)-16:int(next()%65536)-32768):0;
  }
  if(t%5==4)v[(t%2)*64+5*8+(t%8)]=int(next()%65535)+1;
  for(int ci=1;ci<3;ci++)for(int k=0;k<64;k++)c.quant_tbl_ptrs[c.comp_info[ci].quant_tbl_no]->quantval[k]=1+next()%(t>=10000?16:(t%2?65535:255));
  setup();check(v);
 }
 std::printf("{\"captured_pairs\":%zu,\"synthetic_pairs\":20000,\"changed_quantizers\":20000,\"unaligned_padded_output\":true,\"byte_exact_to_reduced_reference\":true}\n",pairs.size());
 jpeg_destroy_decompress(&c);jpeg_destroy_decompress(&d);
}
