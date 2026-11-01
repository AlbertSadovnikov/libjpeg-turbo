// Batch-timed component reconstruction and NV12 packing. No per-block clocks.
#define JPEG_INTERNALS
#define main original_nv12_benchmark_main
#include "../../../../benchmarks/nv12_bench.cc"
#undef main
#include <chrono>
#include <array>

struct alignas(32) SavedBlock { JCOEF data[64]; };
struct Plane {
  unsigned w=0,h=0;
  std::vector<SavedBlock> blocks;
  std::vector<unsigned char> pixels;
  std::vector<JSAMPROW> rows;
};
struct Captured {
  std::array<Plane,3> planes;
  Captured() {
    jpeg_decompress_struct c{};jpeg_error_mgr err{};c.err=jpeg_std_error(&err);
    jpeg_create_decompress(&c);jpeg_mem_src(&c,kJpeg,kJpegSize);
    Check(jpeg_read_header(&c,TRUE)==JPEG_HEADER_OK,"Coefficient header");
    auto arrays=jpeg_read_coefficients(&c);Check(arrays,"Coefficient capture");
    for(int ci=0;ci<3;ci++) {
      auto &p=planes[ci];p.w=c.comp_info[ci].width_in_blocks;p.h=c.comp_info[ci].height_in_blocks;
      p.blocks.resize(p.w*p.h);p.pixels.resize(p.w*8*p.h*8);p.rows.resize(p.h*8);
      for(unsigned y=0;y<p.rows.size();y++)p.rows[y]=p.pixels.data()+y*p.w*8;
      for(unsigned y=0;y<p.h;y++) {
        auto row=c.mem->access_virt_barray((j_common_ptr)&c,arrays[ci],y,1,FALSE);
        for(unsigned x=0;x<p.w;x++)std::memcpy(p.blocks[y*p.w+x].data,row[0][x],sizeof(JBLOCK));
      }
    }
    Check(jpeg_finish_decompress(&c),"Coefficient finish");jpeg_destroy_decompress(&c);
  }
};
template<class F> double Batch(F fn) {
  for(int i=0;i<5;i++)fn();
  unsigned n=0;auto begin=std::chrono::steady_clock::now(),end=begin;
  do { for(int i=0;i<8;i++){fn();benchmark::ClobberMemory();n++;}
       end=std::chrono::steady_clock::now();
  } while(std::chrono::duration<double>(end-begin).count()<0.2);
  return std::chrono::duration<double,std::milli>(end-begin).count()/n;
}
int main() {
  width=1920;height=1080;subsamp=TJSAMP_422;
  try {
    Captured saved;auto pack=SimdPack();std::vector<unsigned char> nv12(width*height*3/2),uv(width*height/2);
    std::printf("{\"mcus\":16200,\"planes\":[");
    for(int ci=0;ci<3;ci++) {
      auto &p=saved.planes[ci];unsigned dc_only=0;unsigned long ac=0;
      for(const auto &b:p.blocks){unsigned count=0;for(int k=1;k<64;k++)count+=b.data[k]!=0;ac+=count;dc_only+=count==0;}
      std::printf("%s{\"blocks\":%zu,\"dc_only\":%u,\"nonzero_ac\":%lu}",ci?",":"",p.blocks.size(),dc_only,ac);
    }
    std::printf("],\"modes\":{");
    for(int fast=0;fast<2;fast++) {
      Strips reference(fast);reference.Decode(nv12,pack);
      jpeg_decompress_struct c{};jpeg_error_mgr err{};c.err=jpeg_std_error(&err);
      jpeg_create_decompress(&c);jpeg_mem_src(&c,kJpeg,kJpegSize);Check(jpeg_read_header(&c,TRUE)==JPEG_HEADER_OK,"IDCT header");
      c.raw_data_out=TRUE;c.dct_method=fast?JDCT_IFAST:JDCT_ISLOW;Check(jpeg_start_decompress(&c),"IDCT setup");
      auto idct=[&](int ci){
        auto &p=saved.planes[ci];auto method=c.idct->inverse_DCT[ci];
        for(unsigned y=0;y<p.h;y++)for(unsigned x=0;x<p.w;x++)
          method(&c,&c.comp_info[ci],p.blocks[y*p.w+x].data,p.rows.data()+y*8,x*8);
      };
      for(int ci=0;ci<3;ci++)idct(ci);
      Check(std::memcmp(saved.planes[0].pixels.data(),nv12.data(),width*height)==0,"Y reconstruction mismatch");
      auto packing=[&]{pack(uv.data(),saved.planes[1].pixels.data(),saved.planes[2].pixels.data(),width/2,width,width/2,height/2,true);};
      packing();Check(std::memcmp(uv.data(),nv12.data()+width*height,uv.size())==0,"UV reconstruction mismatch");
      double full=Batch([&]{reference.Decode(nv12,pack);});
      double times[3];for(int ci=0;ci<3;ci++)times[ci]=Batch([&]{idct(ci);});
      double uv_idct=Batch([&]{idct(1);idct(2);});
      double packed=Batch(packing);
      std::printf("%s\"%s\":{\"full_ms\":%.9f,\"Y_idct_ms\":%.9f,\"Cb_idct_ms\":%.9f,\"Cr_idct_ms\":%.9f,\"UV_idct_ms\":%.9f,\"halve_interleave_ms\":%.9f}",fast?",":"",fast?"fast":"accurate",full,times[0],times[1],times[2],uv_idct,packed);
      jpeg_abort_decompress(&c);jpeg_destroy_decompress(&c);
    }
    std::printf("}}\n");
  } catch(const std::exception &e){std::fprintf(stderr,"%s\n",e.what());return 1;}
}
