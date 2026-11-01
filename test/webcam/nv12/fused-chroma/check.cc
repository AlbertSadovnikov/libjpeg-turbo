// UV-only kernel checks: exact native reference and a double-precision oracle.
#include <cstdio>
#include <cstddef>
#define JPEG_INTERNALS
#include "jpeglib.h"
#include "fusion.h"
#include "embedded_frame.h"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <cstdint>
#include <vector>
extern "C" void mjpeg_chroma_exact(const void*,const void*,const JCOEF*,const JCOEF*,unsigned char*,int);
int main(){
  jpeg_decompress_struct c{};jpeg_error_mgr error{};c.err=jpeg_std_error(&error);jpeg_create_decompress(&c);
  jpeg_mem_src(&c,mjpeg_bench::kJpeg,mjpeg_bench::kJpegSize);jpeg_read_header(&c,TRUE);
  c.raw_data_out=TRUE;c.dct_method=JDCT_ISLOW;jpeg_start_decompress(&c);
  constexpr int pitch=35;unsigned char output[pitch*4+8];
  std::vector<unsigned char> registered_uv(c.image_width*c.image_height/2);
  if(!mjpeg_fusion_begin(&c,registered_uv.data(),c.image_width,2))return 2;
  alignas(32) JCOEF blocks[2][64];unsigned char planes[2][64];JSAMPROW rows[2][8];
  for(int ci=0;ci<2;ci++)for(int y=0;y<8;y++)rows[ci][y]=planes[ci]+8*y;
  uint32_t rng=123456789;auto next=[&]{rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;};
  double weights[4][8][64];const double pi=std::acos(-1.0);
  for(int y=0;y<4;y++)for(int x=0;x<8;x++)for(int v=0;v<8;v++)for(int u=0;u<8;u++){
    double ax=u?1:1/std::sqrt(2.),ay=v?1:1/std::sqrt(2.);
    weights[y][x][v*8+u]=.125*ax*ay*std::cos((2*x+1)*u*pi/16)*
       (std::cos((4*y+1)*v*pi/16)+std::cos((4*y+3)*v*pi/16));
  }
  int oracle_peak=0;
  for(int trial=0;trial<10000;trial++){
    std::memset(blocks,0,sizeof(blocks));
    for(int ci=0;ci<2;ci++){
      blocks[ci][0]=int(next()%2049)-1024;
      for(int k=1;k<64;k++){
        if(trial%5==0)continue;
        if(trial%5==1&&k>=8)continue;
        if(trial%5==2&&k%8)continue;
        if(trial%5==3&&next()%8)continue;
        blocks[ci][k]=int(next()%129)-64;
      }
      c.idct->inverse_DCT[ci+1](&c,&c.comp_info[ci+1],blocks[ci],rows[ci],0);
    }
    std::memset(output,0xa5,sizeof(output));
    mjpeg_chroma_exact(c.comp_info[1].dct_table,c.comp_info[2].dct_table,blocks[0],blocks[1],output+3,pitch);
    for(int y=0;y<4;y++)for(int x=0;x<8;x++)for(int ci=0;ci<2;ci++){
      unsigned expected=(planes[ci][y*16+x]+planes[ci][y*16+8+x]+1)/2;
      if(output[3+y*pitch+2*x+ci]!=expected){std::fprintf(stderr,"Exact mismatch trial=%d\n",trial);return 1;}
    }
    for(unsigned i=0;i<sizeof(output);i++){
      bool pixel=false;for(int y=0;y<4;y++)pixel|=i>=unsigned(3+y*pitch)&&i<unsigned(3+y*pitch+16);
      if(!pixel&&output[i]!=0xa5)return 3;
    }
    if(trial<500){
      mjpeg_chroma_reduced_test(blocks[0],blocks[1],output+3,pitch);
      for(int y=0;y<4;y++)for(int x=0;x<8;x++)for(int ci=0;ci<2;ci++){
        double sum=128.;auto*q=c.quant_tbl_ptrs[c.comp_info[ci+1].quant_tbl_no];
        for(int k=0;k<64;k++)sum+=weights[y][x][k]*blocks[ci][k]*q->quantval[k];
        int expected=std::clamp(int(std::floor(sum+.5)),0,255);
        int d=std::abs(int(output[3+y*pitch+2*x+ci])-expected);oracle_peak=std::max(oracle_peak,d);
        if(d>1){std::fprintf(stderr,"Oracle mismatch %d trial=%d\n",d,trial);return 4;}
      }
    }
  }
  std::printf("{\"exact_random_pairs\":10000,\"reduced_double_oracle_pairs\":500,\"oracle_max_abs\":%d,\"padding\":\"pass\"}\n",oracle_peak);
  mjpeg_fusion_end();jpeg_abort_decompress(&c);jpeg_destroy_decompress(&c);
}
