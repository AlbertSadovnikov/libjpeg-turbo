// Serialize every quantized coefficient for literal control/candidate comparison.
#include <cstdio>
#include <cstdlib>
#include <cstddef>
#define JPEG_INTERNALS
#include "jpeglib.h"
#include <fstream>
#include <iterator>
#include <vector>
#include <cstdint>
extern "C" int mjpeg_fusion_mcu(j_decompress_ptr,JBLOCKROW *,JSAMPIMAGE,JDIMENSION){return 0;}
static void write(const void *p,size_t n){if(std::fwrite(p,1,n,stdout)!=n)std::exit(2);}
static void number(uint32_t n){write(&n,sizeof(n));}
int main(int argc,char **argv){
 if(argc!=2)return 2;
 std::ifstream f(argv[1],std::ios::binary);if(!f)return 2;
 std::vector<unsigned char> bytes((std::istreambuf_iterator<char>(f)),{});
 jpeg_decompress_struct c{};jpeg_error_mgr e{};c.err=jpeg_std_error(&e);jpeg_create_decompress(&c);
 jpeg_mem_src(&c,bytes.data(),bytes.size());if(jpeg_read_header(&c,TRUE)!=JPEG_HEADER_OK)return 2;
 auto a=jpeg_read_coefficients(&c);if(!a)return 2;
 number(c.image_width);number(c.image_height);number(c.num_components);number(c.data_precision);
 for(int ci=0;ci<c.num_components;ci++){
  auto &p=c.comp_info[ci];number(p.width_in_blocks);number(p.height_in_blocks);number(p.quant_tbl_no);
  write(c.quant_tbl_ptrs[p.quant_tbl_no]->quantval,64*sizeof(UINT16));
  for(unsigned y=0;y<p.height_in_blocks;y++){
   auto row=c.mem->access_virt_barray((j_common_ptr)&c,a[ci],y,1,FALSE);
   write(row[0],p.width_in_blocks*sizeof(JBLOCK));
  }
 }
 if(!jpeg_finish_decompress(&c)||e.num_warnings)return 2;
 jpeg_destroy_decompress(&c);return 0;
}
