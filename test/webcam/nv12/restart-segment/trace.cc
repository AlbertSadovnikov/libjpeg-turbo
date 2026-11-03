#include <cstdio>
#include <cstddef>
#define JPEG_INTERNALS
#include "jpeglib.h"
#include <vector>
#include <fstream>
#include <iterator>
#include <cstdlib>
#include <cstring>
#include <cstdint>
extern "C" int mjpeg_segment_enabled;
extern "C" int mjpeg_segment_install(j_decompress_ptr);
static unsigned long long mcus=0;
static void require(bool b){if(!b)std::exit(2);}
static void write(const void*p,size_t n){require(std::fwrite(p,1,n,stdout)==n);}
static void number(uint32_t n){write(&n,sizeof(n));}
extern "C" int mjpeg_fusion_mcu(j_decompress_ptr c,JBLOCKROW *b,JSAMPIMAGE,JDIMENSION col){
 number(c->input_iMCU_row);number(col);for(int j=0;j<c->blocks_in_MCU;j++)write(*b[j],sizeof(JBLOCK));mcus++;return 1;
}
int main(int argc,char**argv){require(argc==2);const char *flag=std::getenv("MJPEG_SEGMENT");mjpeg_segment_enabled=!(flag&&std::strcmp(flag,"0")==0);
 std::ifstream in(argv[1],std::ios::binary);require(bool(in));std::vector<unsigned char> jpeg{std::istreambuf_iterator<char>(in),{}};
 jpeg_decompress_struct c{};jpeg_error_mgr e{};c.err=jpeg_std_error(&e);jpeg_create_decompress(&c);jpeg_mem_src(&c,jpeg.data(),jpeg.size());require(jpeg_read_header(&c,TRUE)==JPEG_HEADER_OK);c.raw_data_out=TRUE;c.dct_method=JDCT_IFAST;require(jpeg_start_decompress(&c));
 require(c.num_components==3&&c.max_h_samp_factor==2&&c.max_v_samp_factor==1&&c.data_precision==8);
 number(c.image_width);number(c.image_height);number(c.num_components);
 for(int j=0;j<3;j++){number(c.comp_info[j].quant_tbl_no);write(c.quant_tbl_ptrs[c.comp_info[j].quant_tbl_no]->quantval,64*sizeof(UINT16));}
 int selected=mjpeg_segment_install(&c);std::vector<unsigned char> data[3];JSAMPROW rows[3][8];JSAMPARRAY planes[3];
 for(int j=0;j<3;j++){int pitch=c.comp_info[j].width_in_blocks*8;data[j].resize(pitch*8);planes[j]=rows[j];for(int i=0;i<8;i++)rows[j][i]=data[j].data()+pitch*i;}
 while(c.output_scanline<c.output_height)require(jpeg_read_raw_data(&c,planes,8)!=0);
 require(jpeg_finish_decompress(&c));require(e.num_warnings==0);jpeg_destroy_decompress(&c);number(mcus);
 std::fprintf(stderr,"{\"selected\":%d,\"mcus\":%llu}\n",selected,mcus);
}
