#include <cstdio>
#include <cstddef>
#define JPEG_INTERNALS
#include "jpeglib.h"
#include "fusion.h"
#include "jdcoefct.h"
#include <vector>
#include <fstream>
#include <iterator>
#include <algorithm>
#include <cstring>
#include <cstdlib>
#include <cstdint>
static void require(bool b){if(!b){std::fprintf(stderr,"two-MCU check failed\n");std::exit(1);}}
static boolean suspend(j_decompress_ptr){return FALSE;}
struct Result {std::vector<unsigned char> y,uv;unsigned pauses=0,odd=0;};
static Result decode(const std::vector<unsigned char>&jpeg,size_t chunk){
 jpeg_decompress_struct c{};jpeg_error_mgr e{};c.err=jpeg_std_error(&e);jpeg_create_decompress(&c);
 jpeg_mem_src(&c,jpeg.data(),jpeg.size());require(jpeg_read_header(&c,TRUE)==JPEG_HEADER_OK);
 c.raw_data_out=TRUE;c.dct_method=JDCT_IFAST;require(jpeg_start_decompress(&c));
 const int w=c.output_width,h=c.output_height,yp=w+13,up=w+29;
 require(w%16==0&&h%8==0&&c.max_v_samp_factor==1&&c.max_h_samp_factor==2);
 Result r;r.y.assign(yp*h,0xa5);r.uv.assign(up*h/2,0xa5);
 const bool fused=mjpeg_fusion_begin(&c,r.uv.data(),up,3);
 std::vector<unsigned char> u(w/2*8),v(u.size());JSAMPROW yr[8],ur[8],vr[8];JSAMPARRAY planes[]={yr,ur,vr};
 for(int i=0;i<8;i++){ur[i]=u.data()+i*w/2;vr[i]=v.data()+i*w/2;}
 const auto *end=jpeg.data()+jpeg.size();const unsigned char *frontier=end;
 if(chunk){frontier=std::min(end,c.src->next_input_byte+std::min(chunk,size_t(end-c.src->next_input_byte)));c.src->bytes_in_buffer=frontier-c.src->next_input_byte;c.src->fill_input_buffer=suspend;}
 while(c.output_scanline<c.output_height){
  int row=c.output_scanline;for(int i=0;i<8;i++)yr[i]=r.y.data()+(row+i)*yp;
  if(!jpeg_read_raw_data(&c,planes,8)){
   require(chunk&&frontier<end);r.pauses++;r.odd+=((my_coef_controller*)c.coef)->MCU_ctr%2;
   frontier+=std::min(chunk,size_t(end-frontier));require(frontier>=c.src->next_input_byte);c.src->bytes_in_buffer=frontier-c.src->next_input_byte;continue;
  }
  if(!fused)for(int y=0;y<4;y++)for(int x=0;x<w/2;x++){
   r.uv[(row/2+y)*up+2*x]=(ur[2*y][x]+ur[2*y+1][x]+1)/2;
   r.uv[(row/2+y)*up+2*x+1]=(vr[2*y][x]+vr[2*y+1][x]+1)/2;
  }
 }
 if(chunk){c.src->bytes_in_buffer=end-c.src->next_input_byte;}
 require(jpeg_finish_decompress(&c));require(e.num_warnings==0);mjpeg_fusion_end();jpeg_destroy_decompress(&c);
 for(int y=0;y<h;y++)for(int x=w;x<yp;x++)require(r.y[y*yp+x]==0xa5);
 for(int y=0;y<h/2;y++)for(int x=w;x<up;x++)require(r.uv[y*up+x]==0xa5);
 return r;
}
int main(int argc,char **argv){require(argc>=2);unsigned long long pauses=0,odd=0;uint64_t hash=14695981039346656037ULL;
 for(int i=1;i<argc;i++){
  std::ifstream in(argv[i],std::ios::binary);require(bool(in));std::vector<unsigned char> jpg{std::istreambuf_iterator<char>(in),{}};
  auto ref=decode(jpg,0);for(size_t chunk:{size_t(97),size_t(4093)}){auto r=decode(jpg,chunk);require(r.y==ref.y&&r.uv==ref.uv);pauses+=r.pauses;odd+=r.odd;}
  for(auto *p:{&ref.y,&ref.uv})for(auto b:*p){hash^=b;hash*=1099511628211ULL;}
 }
 std::printf("{\"files\":%d,\"suspensions\":%llu,\"odd_resume_columns\":%llu,\"hash\":\"%016llx\"}\n",argc-1,pauses,odd,(unsigned long long)hash);
}
