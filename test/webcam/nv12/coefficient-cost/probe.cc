// Diagnostic counters and batch-only timing of the retained MCU controller.
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
#include <algorithm>
#include <stdexcept>
extern "C" void mjpeg_idct_ifast_pair(const void *,const JCOEF *,const JCOEF *,JSAMPARRAY,unsigned);
extern "C" void jzero_far(void *,size_t);
static void require(bool b,const char *s){if(!b)throw std::runtime_error(s);}
struct alignas(64) MCU {JCOEF b[4][64];};
static std::vector<MCU> trace;
static std::vector<MCU> expected;
static size_t expected_mcu=0;
struct Counts {uint64_t blocks=0,nz=0,ac=0,dc_zero=0,lines=0,store_lines=0;uint64_t hist[64]{};};
static Counts counts[3];
static bool diagnostic=false,save=false;
static uint64_t mcus=0,cleared=0,clear_lines=0,alignments[64]{};
// Replace reconstruction only. The actual retained controller still clears and
// entropy-decodes every MCU. Its coefficient buffer is never changed here.
extern "C" int mjpeg_fusion_mcu(j_decompress_ptr c,JBLOCKROW *b,JSAMPIMAGE,JDIMENSION){
  if(!diagnostic)return 1;
  require(c->blocks_in_MCU==4,"Expected four-block MCU");
  require(expected_mcu<expected.size(),"Extra diagnostic MCU");
  for(int j=0;j<4;j++)require(!std::memcmp(*b[j],expected[expected_mcu].b[j],sizeof(JBLOCK)),"Coefficient API mismatch");
  ++expected_mcu;
  ++mcus;cleared+=4*sizeof(JBLOCK);
  auto addr=reinterpret_cast<uintptr_t>(b[0]);++alignments[addr%64];
  clear_lines+=((addr%64)+4*sizeof(JBLOCK)+63)/64;
  uint64_t nzmask=0,storemask=0;
  for(int j=0;j<4;j++){
    auto &s=counts[j<2?0:j-1];++s.blocks;int ac=0;
    uint64_t nl=0,sl=0;
    for(int k=0;k<64;k++){
      auto line=(reinterpret_cast<uintptr_t>(&(*b[j])[k])-(addr&~uintptr_t(63)))/64;
      require(line<64,"Line mask overflow");
      bool n=(*b[j])[k]!=0;
      s.nz+=n;if(k)ac+=n;else s.dc_zero+=!n;
      if(n)nl|=uint64_t(1)<<line;
      if(n||k==0)sl|=uint64_t(1)<<line;
    }
    s.ac+=ac;++s.hist[ac];s.lines+=__builtin_popcountll(nl);s.store_lines+=__builtin_popcountll(sl);
    nzmask|=nl;storemask|=sl;
  }
  // Per-component line counts can share physical lines if the buffer is not
  // aligned; global masks below give unique lines per MCU.
  extern uint64_t nz_lines,store_lines;
  nz_lines+=__builtin_popcountll(nzmask);store_lines+=__builtin_popcountll(storemask);
  if(save){MCU v;for(int j=0;j<4;j++)std::memcpy(v.b[j],*b[j],sizeof(JBLOCK));trace.push_back(v);}
  return 1;
}
uint64_t nz_lines=0,store_lines=0;
struct Decoder {
  jpeg_decompress_struct c{};jpeg_error_mgr e{};
  unsigned char scratch[3][8][1920]{};JSAMPROW rows[3][8];JSAMPARRAY image[3];
  Decoder(){c.err=jpeg_std_error(&e);jpeg_create_decompress(&c);for(int j=0;j<3;j++){image[j]=rows[j];for(int y=0;y<8;y++)rows[j][y]=scratch[j][y];}}
  ~Decoder(){jpeg_destroy_decompress(&c);}
  void begin(const std::vector<unsigned char>&v){jpeg_mem_src(&c,v.data(),v.size());require(jpeg_read_header(&c,TRUE)==JPEG_HEADER_OK,"Header");require(c.image_width==1920&&c.image_height==1080&&!c.progressive_mode&&!c.restart_interval,"Capture geometry");c.raw_data_out=TRUE;c.dct_method=JDCT_IFAST;require(jpeg_start_decompress(&c),"Start");}
  void body(){while(c.output_scanline<c.output_height)require(jpeg_read_raw_data(&c,image,8)==8,"Raw read");require(e.num_warnings==0,"Warnings");}
  void finish(){require(jpeg_finish_decompress(&c),"Finish");}
};
static void reference(const std::vector<unsigned char>&v){
  jpeg_decompress_struct c{};jpeg_error_mgr e{};c.err=jpeg_std_error(&e);jpeg_create_decompress(&c);
  jpeg_mem_src(&c,v.data(),v.size());require(jpeg_read_header(&c,TRUE)==JPEG_HEADER_OK,"Reference header");
  auto a=jpeg_read_coefficients(&c);require(a,"Reference coefficients");
  expected.resize(16200);expected_mcu=0;
  for(unsigned y=0;y<135;y++){
    JBLOCKARRAY row[3];for(int j=0;j<3;j++)row[j]=c.mem->access_virt_barray((j_common_ptr)&c,a[j],y,1,FALSE);
    for(unsigned x=0;x<120;x++)for(int j=0;j<4;j++){
      int ci=j<2?0:j-1;unsigned col=j<2?2*x+j:x;
      std::memcpy(expected[y*120+x].b[j],row[ci][0][col],sizeof(JBLOCK));
    }
  }
  require(jpeg_finish_decompress(&c)&&e.num_warnings==0,"Reference finish");jpeg_destroy_decompress(&c);
}
template<class F> double batch(F f){for(int i=0;i<5;i++)f();int n=0;auto a=std::chrono::steady_clock::now(),b=a;do{for(int i=0;i<8;i++){f();++n;}b=std::chrono::steady_clock::now();}while(std::chrono::duration<double>(b-a).count()<0.2);return std::chrono::duration<double,std::nano>(b-a).count()/n;}
static inline void escape(void *p){asm volatile(""::"r"(p):"memory");}
int main(int argc,char **argv){try{
  require(argc>2,"count|entropy|kernels files...");std::string mode=argv[1];
  std::vector<std::vector<unsigned char>> frames;
  for(int i=2;i<argc;i++){std::ifstream f(argv[i],std::ios::binary);require(bool(f),"Input read");frames.emplace_back(std::istreambuf_iterator<char>(f),std::istreambuf_iterator<char>());}
  Decoder d;
  if(mode=="count"||mode=="kernels"){
    diagnostic=true;
    for(size_t i=0;i<frames.size();i++){reference(frames[i]);save=mode=="kernels";d.begin(frames[i]);d.body();d.finish();require(expected_mcu==expected.size(),"Missing diagnostic MCUs");}
    diagnostic=false;save=false;
  }
  if(mode=="count"){
    std::printf("{\"frames\":%zu,\"mcus\":%llu,\"cleared_bytes\":%llu,\"clear_cache_lines\":%llu,\"nonzero_cache_lines\":%llu,\"unique_store_cache_lines\":%llu,\"buffer_alignments\":[",frames.size(),(unsigned long long)mcus,(unsigned long long)cleared,(unsigned long long)clear_lines,(unsigned long long)nz_lines,(unsigned long long)store_lines);
    for(int i=0;i<64;i++)std::printf("%s%llu",i?",":"",(unsigned long long)alignments[i]);std::printf("],\"components\":[");
    for(int j=0;j<3;j++){auto &s=counts[j];std::printf("%s{\"blocks\":%llu,\"nonzero\":%llu,\"nonzero_ac\":%llu,\"zero_dc\":%llu,\"nonzero_lines\":%llu,\"store_lines\":%llu,\"ac_histogram\":[",j?",":"",(unsigned long long)s.blocks,(unsigned long long)s.nz,(unsigned long long)s.ac,(unsigned long long)s.dc_zero,(unsigned long long)s.lines,(unsigned long long)s.store_lines);for(int i=0;i<64;i++)std::printf("%s%llu",i?",":"",(unsigned long long)s.hist[i]);std::printf("]}");}std::puts("]}");
  }else if(mode=="entropy"){
    // Start/table setup and finish are outside each full-frame body timer.
    // No per-MCU or symbol clocks and no diagnostics in the timed path.
    std::printf("{\"frames\":%zu,\"rounds\":[",frames.size());
    for(int r=-1;r<5;r++){double ns=0;for(auto &v:frames){d.begin(v);auto a=std::chrono::steady_clock::now();d.body();auto b=std::chrono::steady_clock::now();d.finish();ns+=std::chrono::duration<double,std::nano>(b-a).count();}if(r>=0)std::printf("%s%.9f",r?",":"",ns/frames.size()/1e6);}
    std::puts("]}");
  }else if(mode=="kernels"){
    require(frames.size()==1,"One trace frame");d.begin(frames[0]);
    unsigned char uv[4][1920]{};require(mjpeg_fusion_begin(&d.c,&uv[0][0],1920,2),"Reduced kernel setup");
    // Precomputed unique stores in JPEG zigzag order, including zero DC.
    extern const int jpeg_natural_order[];
    struct Store{uint16_t offset;JCOEF value;};std::vector<Store> stores;std::vector<size_t> ends;
    for(auto &v:trace){for(int j=0;j<4;j++)for(int z=0;z<64;z++){int k=jpeg_natural_order[z];if(z==0||v.b[j][k])stores.push_back({uint16_t(j*64+k),v.b[j][k]});}ends.push_back(stores.size());}
    alignas(64) unsigned char area[640];size_t alignment=0;for(int i=0;i<64;i++)if(alignments[i])alignment=i;auto *buffer=reinterpret_cast<JCOEF*>(area+alignment);
    auto replay=[&](bool clear){size_t start=0;for(size_t end:ends){if(clear)jzero_far(buffer,512);for(size_t k=start;k<end;k++)buffer[stores[k].offset]=stores[k].value;escape(buffer);start=end;}};
    auto pair=[&](){for(auto &v:trace)mjpeg_idct_ifast_pair(d.c.comp_info[0].dct_table,v.b[0],v.b[1],d.rows[0],3);};
    auto chroma=[&](){for(auto &v:trace)mjpeg_chroma_reduced_test(v.b[2],v.b[3],&uv[0][0],1920);};
    std::printf("{\"mcus\":%zu,\"store_records\":%zu,\"alignment\":%zu,\"rounds\":[",trace.size(),stores.size(),alignment);
    for(int r=0;r<5;r++){
      double clear=batch([&]{for(size_t i=0;i<trace.size();i++){jzero_far(buffer,512);escape(buffer);}});
      double a,b;if(r%2){b=batch([&]{replay(false);});a=batch([&]{replay(true);});}else{a=batch([&]{replay(true);});b=batch([&]{replay(false);});}
      double y,u;if(r%2){u=batch(chroma);y=batch(pair);}else{y=batch(pair);u=batch(chroma);}
      std::printf("%s{\"clear_ns_mcu\":%.6f,\"clear_scatter_ns_mcu\":%.6f,\"scatter_only_ns_mcu\":%.6f,\"paired_y_ns_mcu\":%.6f,\"reduced_uv_ns_mcu\":%.6f}",r?",":"",clear/trace.size(),a/trace.size(),b/trace.size(),y/trace.size(),u/trace.size());
    }
    std::puts("]}");mjpeg_fusion_end();jpeg_abort_decompress(&d.c);
  }else require(false,"Unknown mode");
}catch(const std::exception &e){std::fprintf(stderr,"%s\n",e.what());return 1;}}
