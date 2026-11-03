// Batch stage timings and untimed real-MCU chroma sparsity counters.
#include <cstdio>
#include <cstdlib>
#include <cstddef>
#define JPEG_INTERNALS
#include "jpeglib.h"
#include "fusion.h"
#include <array>
#include <vector>
#include <fstream>
#include <iterator>
#include <chrono>
#include <cstring>
#include <cstdint>
#include <stdexcept>
extern "C" { unsigned long long mjpeg_diag[11]{}; }
extern "C" void mjpeg_idct_ifast_registers(const void*,const JCOEF*,const JCOEF*,JSAMPARRAY,unsigned);
struct alignas(32) MCU {JCOEF b[4][64];};
static std::vector<MCU> trace;
static bool collect=false,keep=false;
static uint64_t mcus=0,zero[8][2]{},high_zero[2]{},nonzero[3]{};
static void check(bool x,const char *s){if(!x)throw std::runtime_error(s);}
extern "C" int mjpeg_fusion_mcu(j_decompress_ptr c,JBLOCKROW *b,JSAMPIMAGE,JDIMENSION){
 if(!collect)return 1;
 check(c->blocks_in_MCU==4,"MCU geometry");++mcus;
 for(int j=0;j<4;j++)for(int k=0;k<64;k++)nonzero[j<2?0:j-1]+=(*b[j])[k]!=0;
 for(int half=0;half<2;half++){
  bool high=true;
  for(int v=0;v<8;v++){
   bool z=true;for(int k=0;k<4;k++)z&=((*b[2])[v*8+half*4+k]==0 && (*b[3])[v*8+half*4+k]==0);
   zero[v][half]+=z;if(v>=5)high&=z;
  }
  high_zero[half]+=high;
 }
 if(keep){MCU v;for(int j=0;j<4;j++)std::memcpy(v.b[j],*b[j],sizeof(JBLOCK));trace.push_back(v);}
 return 1;
}
struct Decoder{
 jpeg_decompress_struct c{};jpeg_error_mgr e{};unsigned char pixels[3][8][1920]{};JSAMPROW rows[3][8];JSAMPARRAY image[3];
 Decoder(){c.err=jpeg_std_error(&e);jpeg_create_decompress(&c);for(int j=0;j<3;j++){image[j]=rows[j];for(int y=0;y<8;y++)rows[j][y]=pixels[j][y];}}
 ~Decoder(){jpeg_destroy_decompress(&c);}
 void begin(const std::vector<unsigned char>&b){jpeg_mem_src(&c,b.data(),b.size());check(jpeg_read_header(&c,TRUE)==JPEG_HEADER_OK,"header");check(c.image_width==1920&&c.image_height==1080&&!c.progressive_mode,"geometry");c.raw_data_out=TRUE;c.dct_method=JDCT_IFAST;check(jpeg_start_decompress(&c),"start");}
 void body(){while(c.output_scanline<c.output_height)check(jpeg_read_raw_data(&c,image,8)==8,"raw");check(e.num_warnings==0,"warning");}
 void finish(){check(jpeg_finish_decompress(&c),"finish");}
};
template<class F> double batch(F f){for(int i=0;i<5;i++)f();unsigned n=0;auto a=std::chrono::steady_clock::now(),b=a;do{for(int i=0;i<8;i++){f();++n;}b=std::chrono::steady_clock::now();}while(std::chrono::duration<double>(b-a).count()<0.2);return std::chrono::duration<double,std::nano>(b-a).count()/n;}
int main(int argc,char**argv){try{
 check(argc>2,"count|entropy|kernels JPEGs");std::string mode=argv[1];std::vector<std::vector<unsigned char>> frames;
 for(int i=2;i<argc;i++){std::ifstream f(argv[i],std::ios::binary);check(bool(f),"read");frames.emplace_back(std::istreambuf_iterator<char>(f),std::istreambuf_iterator<char>());}
 Decoder d;
 if(mode=="count"||mode=="kernels"){
  collect=true;keep=mode=="kernels";
  for(auto &v:frames){d.begin(v);d.body();d.finish();}
  collect=false;keep=false;
 }
 if(mode=="count"){
  std::printf("{\"mcus\":%llu,\"nonzero\":[%llu,%llu,%llu],\"zero_half_groups\":[",(unsigned long long)mcus,(unsigned long long)nonzero[0],(unsigned long long)nonzero[1],(unsigned long long)nonzero[2]);
  for(int v=0;v<8;v++)std::printf("%s[%llu,%llu]",v?",":"",(unsigned long long)zero[v][0],(unsigned long long)zero[v][1]);
  std::printf("],\"all_v5_to_v7_zero\":[%llu,%llu],\"entropy_counters\":[",(unsigned long long)high_zero[0],(unsigned long long)high_zero[1]);
  for(int i=0;i<11;i++)std::printf("%s%llu",i?",":"",mjpeg_diag[i]);std::puts("]}");
 }else if(mode=="entropy"){
  std::printf("{\"round_ms\":[");
  for(int r=-1;r<5;r++){double ns=0;for(auto&v:frames){d.begin(v);auto a=std::chrono::steady_clock::now();d.body();auto b=std::chrono::steady_clock::now();d.finish();ns+=std::chrono::duration<double,std::nano>(b-a).count();}if(r>=0)std::printf("%s%.9f",r?",":"",ns/frames.size()/1e6);}
  std::puts("]}");
 }else if(mode=="kernels"){
  check(frames.size()==1,"one trace");d.begin(frames[0]);unsigned char uv[4][1920]{};check(mjpeg_fusion_begin(&d.c,&uv[0][0],1920,2),"UV setup");
  std::printf("{\"mcus\":%zu,\"rounds\":[",trace.size());
  for(int r=0;r<5;r++){
   auto y=[&]{for(auto&v:trace)mjpeg_idct_ifast_registers(d.c.comp_info[0].dct_table,v.b[0],v.b[1],d.rows[0],3);};
   auto u=[&]{for(auto&v:trace)mjpeg_chroma_reduced_test(v.b[2],v.b[3],&uv[0][0],1920);};
   double a,b;if(r%2){b=batch(u);a=batch(y);}else{a=batch(y);b=batch(u);}
   std::printf("%s{\"Y_ns_mcu\":%.6f,\"UV_ns_mcu\":%.6f}",r?",":"",a/trace.size(),b/trace.size());
  }
  std::puts("]}");mjpeg_fusion_end();jpeg_abort_decompress(&d.c);
 }else check(false,"mode");
}catch(const std::exception&e){std::fprintf(stderr,"%s\n",e.what());return 1;}}
