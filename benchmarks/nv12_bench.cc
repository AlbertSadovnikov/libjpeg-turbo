// Full-range NV12 prototypes: no RGB conversion and no runtime JPEG loading.
#include <benchmark/benchmark.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <stdexcept>
#include <string>
#include <vector>
#include "jpeglib.h"
#include "turbojpeg.h"
#include "embedded_frame.h"
#ifdef MJPEG_STB_REFERENCE
#define STB_IMAGE_IMPLEMENTATION
#define STBI_ONLY_JPEG
#define STBI_NO_STDIO
#define STBI_NO_LINEAR
#define STBI_NO_HDR
#include "../extra/stb_image.h"
#endif
#if defined(__x86_64__) && (defined(__GNUC__) || defined(__clang__))
#include <immintrin.h>
#define NV12_AVX2 1
#endif

namespace {
using mjpeg_bench::kJpeg;
using mjpeg_bench::kJpegSize;
int width, height, subsamp;
bool failed=false;
void Check(bool ok, const char *message) { if(!ok) throw std::runtime_error(message); }

void PackScalar(unsigned char *dst, const unsigned char *u, const unsigned char *v,
                int stride, int pitch, int samples, int rows, bool halve)
{
  for(int y=0;y<rows;y++) {
    const auto *a=u+y*stride*(halve?2:1), *b=v+y*stride*(halve?2:1);
    for(int x=0;x<samples;x++) {
      dst[y*pitch+2*x]=halve?(a[x]+a[x+stride]+1)/2:a[x];
      dst[y*pitch+2*x+1]=halve?(b[x]+b[x+stride]+1)/2:b[x];
    }
  }
}
#ifdef NV12_AVX2
__attribute__((target("avx2")))
void PackAvx2(unsigned char *dst, const unsigned char *u, const unsigned char *v,
              int stride, int pitch, int samples, int rows, bool halve)
{
  for(int y=0;y<rows;y++) {
    const auto *a=u+y*stride*(halve?2:1), *b=v+y*stride*(halve?2:1);
    auto *out=dst+y*pitch;
    int x=0;
    for(;x+32<=samples;x+=32) {
      auto uu=_mm256_loadu_si256(reinterpret_cast<const __m256i *>(a+x));
      auto vv=_mm256_loadu_si256(reinterpret_cast<const __m256i *>(b+x));
      if(halve) {
        uu=_mm256_avg_epu8(uu,_mm256_loadu_si256(reinterpret_cast<const __m256i *>(a+x+stride)));
        vv=_mm256_avg_epu8(vv,_mm256_loadu_si256(reinterpret_cast<const __m256i *>(b+x+stride)));
      }
      auto lo=_mm256_unpacklo_epi8(uu,vv), hi=_mm256_unpackhi_epi8(uu,vv);
      _mm256_storeu_si256(reinterpret_cast<__m256i *>(out+2*x),_mm256_permute2x128_si256(lo,hi,0x20));
      _mm256_storeu_si256(reinterpret_cast<__m256i *>(out+2*x+32),_mm256_permute2x128_si256(lo,hi,0x31));
    }
    for(;x<samples;x++) {
      out[2*x]=halve?(a[x]+a[x+stride]+1)/2:a[x];
      out[2*x+1]=halve?(b[x]+b[x+stride]+1)/2:b[x];
    }
  }
}
#endif
using PackFn=decltype(&PackScalar);
PackFn SimdPack()
{
#ifdef NV12_AVX2
  if(__builtin_cpu_supports("avx2")) return PackAvx2;
#endif
  return PackScalar;
}

struct Planar {
  tjhandle handle=tj3Init(TJINIT_DECOMPRESS);
  std::vector<unsigned char> u,v;
  explicit Planar(bool fast):u(width/2*(subsamp==TJSAMP_422?height:height/2)),v(u.size())
  {
    Check(handle!=nullptr,"TurboJPEG init");
    Check(tj3Set(handle,TJPARAM_FASTDCT,fast)==0,"Set IDCT");
  }
  ~Planar() { tj3Destroy(handle); }
  void Decode(std::vector<unsigned char> &dst, PackFn pack)
  { Decode(dst.data(),width,dst.data()+width*height,width,pack); }
  void Decode(unsigned char *y, int y_pitch, unsigned char *uv, int uv_pitch, PackFn pack)
  {
    Check(y && uv && y_pitch>=width && uv_pitch>=width,"Invalid NV12 destination");
    unsigned char *planes[]={y,u.data(),v.data()};
    int strides[]={y_pitch,width/2,width/2};
    Check(tj3DecompressToYUVPlanes8(handle,kJpeg,kJpegSize,planes,strides)==0,
          tj3GetErrorStr(handle));
    pack(uv,u.data(),v.data(),width/2,uv_pitch,width/2,height/2,subsamp==TJSAMP_422);
  }
};

struct Strips {
  jpeg_decompress_struct c{};
  jpeg_error_mgr error{};
  bool fast;
  int yp=(width+7)/8*8, cp=(width/2+7)/8*8;
  std::vector<unsigned char> scratch=std::vector<unsigned char>(yp*16);
  std::vector<unsigned char> u=std::vector<unsigned char>(cp*8),v=u;
  explicit Strips(bool f):fast(f) { c.err=jpeg_std_error(&error); jpeg_create_decompress(&c); }
  ~Strips() { jpeg_destroy_decompress(&c); }
  void Decode(std::vector<unsigned char> &dst, PackFn pack,
              const unsigned char *jpeg=kJpeg, std::size_t jpeg_size=kJpegSize)
  { Decode(dst.data(),width,dst.data()+width*height,width,pack,jpeg,jpeg_size); }
  void Decode(unsigned char *y_plane, int y_pitch, unsigned char *uv, int uv_pitch, PackFn pack,
              const unsigned char *jpeg=kJpeg, std::size_t jpeg_size=kJpegSize)
  {
    Check(y_plane && uv && y_pitch>=width && uv_pitch>=width,"Invalid NV12 destination");
    jpeg_mem_src(&c,jpeg,jpeg_size);
    Check(jpeg_read_header(&c,TRUE)==JPEG_HEADER_OK,"JPEG header");
    Check(c.image_width==static_cast<unsigned>(width) && c.image_height==static_cast<unsigned>(height) &&
          c.num_components==3 && c.jpeg_color_space==JCS_YCbCr,"Unexpected JPEG geometry/color");
    Check(c.comp_info[0].h_samp_factor==2 &&
          c.comp_info[0].v_samp_factor==(subsamp==TJSAMP_422?1:2) &&
          c.comp_info[1].h_samp_factor==1 && c.comp_info[1].v_samp_factor==1 &&
          c.comp_info[2].h_samp_factor==1 && c.comp_info[2].v_samp_factor==1,"Unsupported sampling");
    c.raw_data_out=TRUE;
    c.dct_method=fast?JDCT_IFAST:JDCT_ISLOW;
    Check(jpeg_start_decompress(&c),"JPEG start");
    Check(c.comp_info[0].width_in_blocks*8==static_cast<unsigned>(yp) &&
          c.comp_info[1].width_in_blocks*8==static_cast<unsigned>(cp) &&
          c.comp_info[2].width_in_blocks==c.comp_info[1].width_in_blocks,"Unexpected raw plane width");
    JSAMPROW yr[16],ur[8],vr[8];
    JSAMPARRAY planes[]={yr,ur,vr};
    for(int i=0;i<8;i++) { ur[i]=u.data()+i*cp; vr[i]=v.data()+i*cp; }
    const int lines=c.max_v_samp_factor*8;
    while(c.output_scanline<c.output_height) {
      const int y=c.output_scanline, valid=std::min(lines,height-y);
      for(int i=0;i<lines;i++)
        yr[i]=(yp==width && i<valid)?y_plane+(y+i)*y_pitch:scratch.data()+i*yp;
      Check(jpeg_read_raw_data(&c,planes,lines)!=0,"Raw JPEG read");
      if(yp!=width)
        for(int i=0;i<valid;i++) std::memcpy(y_plane+(y+i)*y_pitch,yr[i],width);
      pack(uv+y/2*uv_pitch,u.data(),v.data(),cp,uv_pitch,width/2,valid/2,subsamp==TJSAMP_422);
    }
    Check(jpeg_finish_decompress(&c),"JPEG finish");
    Check(error.num_warnings==0,"JPEG warning");
  }
};

#ifdef MJPEG_STB_REFERENCE
// Benchmark-only internal API use: stb has no public native-YCbCr output API.
// Preserve its per-image table construction and plane allocation behavior.
struct StbPlanes {
  stbi__context context{};
  stbi__jpeg jpeg{};
  StbPlanes() { jpeg.s=&context; }
  ~StbPlanes() { stbi__cleanup_jpeg(&jpeg); }
  void Decode(std::vector<unsigned char> &dst,PackFn pack)
  {
    stbi__cleanup_jpeg(&jpeg);
    context=stbi__context{}; jpeg=stbi__jpeg{}; jpeg.s=&context;
    stbi__start_mem(&context,kJpeg,static_cast<int>(kJpegSize));
    stbi__setup_jpeg(&jpeg);
    Check(stbi__decode_jpeg_image(&jpeg)!=0,"stb JPEG decode");
    Check(context.img_n==3 && context.img_x==static_cast<unsigned>(width) &&
          context.img_y==static_cast<unsigned>(height) && jpeg.img_h_max==2 &&
          jpeg.img_comp[0].h==2 && jpeg.img_comp[0].v==(subsamp==TJSAMP_422?1:2) &&
          jpeg.img_comp[1].h==1 && jpeg.img_comp[1].v==1 &&
          jpeg.img_comp[2].h==1 && jpeg.img_comp[2].v==1 &&
          jpeg.img_comp[1].w2==jpeg.img_comp[2].w2,"stb sampling mismatch");
    for(int y=0;y<height;y++)
      std::memcpy(dst.data()+y*width,jpeg.img_comp[0].data+y*jpeg.img_comp[0].w2,width);
    pack(dst.data()+width*height,jpeg.img_comp[1].data,jpeg.img_comp[2].data,
         jpeg.img_comp[1].w2,width,width/2,height/2,subsamp==TJSAMP_422);
    stbi__cleanup_jpeg(&jpeg);
  }
};
#endif

void Validate()
{
  for(bool fast:{false,true}) {
    std::vector<unsigned char> ref(width*height*3/2),actual(ref.size());
    Planar planar(fast); planar.Decode(ref,PackScalar);
    planar.Decode(actual,SimdPack()); Check(ref==actual,"Planar SIMD mismatch");
    Strips strips(fast);
    strips.Decode(actual,PackScalar); Check(ref==actual,"Raw strip mismatch");
    strips.Decode(actual,SimdPack()); Check(ref==actual,"Raw strip SIMD mismatch");
    // Independent, deliberately unaligned output strides, with padding guards.
    const int y_pitch=width+13, uv_pitch=width+29;
    std::vector<unsigned char> ypad(y_pitch*height,0xa5),uvpad(uv_pitch*height/2,0xa5);
    for(bool raw:{false,true}) {
      std::fill(ypad.begin(),ypad.end(),0xa5); std::fill(uvpad.begin(),uvpad.end(),0xa5);
      if(raw) strips.Decode(ypad.data(),y_pitch,uvpad.data(),uv_pitch,SimdPack());
      else planar.Decode(ypad.data(),y_pitch,uvpad.data(),uv_pitch,SimdPack());
      for(int plane=0;plane<2;plane++) {
        const auto &padded=plane?uvpad:ypad;
        int pitch=plane?uv_pitch:y_pitch,rows=plane?height/2:height;
        auto *expected=ref.data()+(plane?width*height:0);
        for(int row=0;row<rows;row++) {
          Check(std::memcmp(padded.data()+row*pitch,expected+row*width,width)==0,"Strided NV12 mismatch");
          for(int x=width;x<pitch;x++) Check(padded[row*pitch+x]==0xa5,"NV12 padding overwrite");
        }
      }
    }
  }
  std::vector<unsigned char> accurate(width*height*3/2),fast(accurate.size());
  Planar a(false),b(true); a.Decode(accurate,PackScalar); b.Decode(fast,PackScalar);
#ifdef MJPEG_STB_REFERENCE
  {
    StbPlanes stb; std::vector<unsigned char> actual(accurate.size());
    stb.Decode(actual,PackScalar);
    std::vector<unsigned char> simd(actual.size()); stb.Decode(simd,SimdPack());
    Check(actual==simd,"stb NV12 SIMD packing mismatch");
    for(int plane=0;plane<2;plane++) {
      std::size_t start=plane?width*height:0,end=plane?accurate.size():width*height;
      unsigned long long sum=0,changed=0; int peak=0;
      for(auto i=start;i<end;i++) {
        int d=std::abs(int(actual[i])-int(accurate[i]));
        peak=std::max(peak,d); sum+=d; changed+=d!=0;
      }
      std::fprintf(stderr,"stb vs accurate NV12 %s: max_abs=%d mean_abs=%.6f changed=%.3f%%\n",
                   plane?"UV":"Y",peak,double(sum)/(end-start),100.*changed/(end-start));
    }
  }
#endif
  if(const char *prefix=std::getenv("MJPEG_NV12_DUMP")) {
    for(int method=0;method<2;method++) {
      const auto &bytes=method?fast:accurate;
      const auto path=std::string(prefix)+(method?".fast.nv12":".accurate.nv12");
      FILE *file=std::fopen(path.c_str(),"wb"); Check(file!=nullptr,"Open NV12 dump");
      const auto written=std::fwrite(bytes.data(),1,bytes.size(),file);
      const int closed=std::fclose(file);
      Check(written==bytes.size() && closed==0,"Write NV12 dump");
    }
  }
  for(int plane=0;plane<2;plane++) {
    const std::size_t start=plane?width*height:0,end=plane?accurate.size():width*height;
    unsigned long long sum=0,squared=0,changed=0; int peak=0;
    for(auto i=start;i<end;i++) {
      int d=std::abs(int(accurate[i])-int(fast[i]));
      peak=std::max(peak,d); sum+=d; squared+=d*d; changed+=d!=0;
    }
    std::fprintf(stderr,"Fast IDCT %s: max_abs=%d mean_abs=%.6f changed=%.3f%% PSNR=%.3f dB\n",
                 plane?"UV":"Y",peak,double(sum)/(end-start),100.*changed/(end-start),
                 squared?10*std::log10(255.*255.*(end-start)/squared):INFINITY);
  }
}

void Register()
{
#ifdef MJPEG_STB_REFERENCE
  benchmark::RegisterBenchmark("MJPEG/STB/NativePlanesToNV12",[](benchmark::State &state) {
    StbPlanes decoder; std::vector<unsigned char> dst(width*height*3/2);
    auto pack=SimdPack(); decoder.Decode(dst,pack);
    for(auto _:state) { decoder.Decode(dst,pack); benchmark::ClobberMemory(); }
    state.SetItemsProcessed(state.iterations());
  })->Unit(benchmark::kMillisecond);
#endif
  benchmark::RegisterBenchmark("MJPEG/Reference/BGR_Accurate",[](benchmark::State &state) {
    Planar decoder(false); std::vector<unsigned char> dst(width*height*3);
    Check(tj3Decompress8(decoder.handle,kJpeg,kJpegSize,dst.data(),width*3,TJPF_BGR)==0,
          "BGR reference decode");
    for(auto _:state) {
      Check(tj3Decompress8(decoder.handle,kJpeg,kJpegSize,dst.data(),width*3,TJPF_BGR)==0,
            "BGR reference decode");
      benchmark::ClobberMemory();
    }
    state.SetItemsProcessed(state.iterations());
  })->Unit(benchmark::kMillisecond);
  for(bool fast:{false,true}) {
    for(int method=0;method<3;method++) {
      std::string name=std::string("MJPEG/NV12/")+(fast?"FastIDCT/":"Accurate/")+
        (method==0?"PlanarThenPack":method==1?"RawStrips_Scalar":"RawStrips_SIMD");
      benchmark::RegisterBenchmark(name.c_str(),[fast,method](benchmark::State &state) {
        try {
          Planar planar(fast); Strips strips(fast);
          std::vector<unsigned char> dst(width*height*3/2);
          PackFn pack=method==1?PackScalar:SimdPack();
          if(method==0) planar.Decode(dst,pack); else strips.Decode(dst,pack);
          for(auto _:state) {
            if(method==0) planar.Decode(dst,pack); else strips.Decode(dst,pack);
            benchmark::ClobberMemory();
          }
          state.SetItemsProcessed(state.iterations());
        } catch(const std::exception &e) { failed=true; state.SkipWithError(e.what()); }
      })->Unit(benchmark::kMillisecond);
    }
  }
  for(bool simd:{false,true}) {
    benchmark::RegisterBenchmark(simd?"MJPEG/NV12/PackOnly_SIMD":"MJPEG/NV12/PackOnly_Scalar",
      [simd](benchmark::State &state) {
        Planar planar(false); std::vector<unsigned char> dst(width*height*3/2);
        planar.Decode(dst,PackScalar); PackFn pack=simd?SimdPack():PackScalar;
        for(auto _:state) {
          pack(dst.data()+width*height,planar.u.data(),planar.v.data(),width/2,width,width/2,height/2,subsamp==TJSAMP_422);
          benchmark::ClobberMemory();
        }
        state.SetItemsProcessed(state.iterations());
      })->Unit(benchmark::kMillisecond);
  }
}
} // namespace

int main(int argc,char **argv)
{
  benchmark::Initialize(&argc,argv);
  if(benchmark::ReportUnrecognizedArguments(argc,argv)) return 1;
  try {
    tjhandle header=tj3Init(TJINIT_DECOMPRESS); Check(header!=nullptr,"Header init");
    if(tj3DecompressHeader(header,kJpeg,kJpegSize)<0) {
      tj3Destroy(header); throw std::runtime_error("JPEG header");
    }
    width=tj3Get(header,TJPARAM_JPEGWIDTH); height=tj3Get(header,TJPARAM_JPEGHEIGHT);
    subsamp=tj3Get(header,TJPARAM_SUBSAMP);
    int precision=tj3Get(header,TJPARAM_PRECISION),color=tj3Get(header,TJPARAM_COLORSPACE);
    tj3Destroy(header);
    if(!(width>0 && height>0 && width%2==0 && height%2==0 && precision==8 && color==TJCS_YCbCr &&
         (subsamp==TJSAMP_422 || subsamp==TJSAMP_420))) {
      std::fprintf(stderr,"NV12 prototype requires even-size 8-bit YCbCr 422 or 420 JPEG\n");
      benchmark::Shutdown(); return 77;
    }
    Validate();
    benchmark::AddCustomContext("output","NV12, full-range JPEG samples, rounded vertical box filter for 422");
    benchmark::AddCustomContext("packing",SimdPack()==PackScalar?"scalar":"AVX2");
    Register(); benchmark::RunSpecifiedBenchmarks();
  } catch(const std::exception &e) { std::fprintf(stderr,"NV12 validation: %s\n",e.what()); return 1; }
  benchmark::Shutdown(); return failed?1:0;
}
