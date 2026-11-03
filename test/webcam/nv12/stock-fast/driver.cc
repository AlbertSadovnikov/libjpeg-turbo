// Public TurboJPEG API + AVX2 4:2:2-to-NV12 conversion, stock codec only.
#define main original_nv12_benchmark_main
#include "../../../../benchmarks/nv12_bench.cc"
#undef main
#include <chrono>
#include <fstream>
#include <iterator>
#include <cstdint>

struct StockFast {
  tjhandle handle=tj3Init(TJINIT_DECOMPRESS);
  std::vector<unsigned char> u=std::vector<unsigned char>(1920/2*1080),v=u;
  StockFast(){Check(handle,"TurboJPEG init");Check(tj3Set(handle,TJPARAM_FASTDCT,1)==0,"Fast IDCT enable");Check(tj3Get(handle,TJPARAM_FASTDCT)==1,"Fast IDCT state");}
  ~StockFast(){tj3Destroy(handle);}
  void Planes(unsigned char*y,int pitch,const std::vector<unsigned char>&jpeg){
    unsigned char *planes[]={y,u.data(),v.data()};int strides[]={pitch,width/2,width/2};
    Check(tj3DecompressToYUVPlanes8(handle,jpeg.data(),jpeg.size(),planes,strides)==0,tj3GetErrorStr(handle));
  }
  void Pack(unsigned char*uv,int pitch,PackFn fn){fn(uv,u.data(),v.data(),width/2,pitch,width/2,height/2,true);}
  void Decode(std::vector<unsigned char>&dst,const std::vector<unsigned char>&jpeg,PackFn fn){Planes(dst.data(),width,jpeg);Pack(dst.data()+width*height,width,fn);}
};
static uint64_t Hash(uint64_t h,const std::vector<unsigned char>&v){for(auto x:v){h^=x;h*=1099511628211ULL;}return h;}
int main(int argc,char**argv){
  if(argc<4)return 2;width=1920;height=1080;subsamp=TJSAMP_422;
  try{
    bool validate=std::string(argv[1])=="validate";int passes=std::atoi(argv[2]);Check(passes>0,"Pass count");
    std::vector<std::vector<unsigned char>> frames;
    tjhandle header=tj3Init(TJINIT_DECOMPRESS);Check(header,"Header init");
    for(int i=3;i<argc;i++){
      std::ifstream f(argv[i],std::ios::binary);Check(bool(f),"Frame read");frames.emplace_back(std::istreambuf_iterator<char>(f),std::istreambuf_iterator<char>());
      auto&jpeg=frames.back();Check(tj3DecompressHeader(header,jpeg.data(),jpeg.size())==0,tj3GetErrorStr(header));
      Check(tj3Get(header,TJPARAM_JPEGWIDTH)==width&&tj3Get(header,TJPARAM_JPEGHEIGHT)==height&&tj3Get(header,TJPARAM_SUBSAMP)==TJSAMP_422&&tj3Get(header,TJPARAM_PRECISION)==8,"Unexpected frame geometry");
    }
    tj3Destroy(header);Check(SimdPack()==PackAvx2,"AVX2 packing unavailable");StockFast decoder;
    std::vector<unsigned char> dst(width*height*3/2),reference(dst.size());uint64_t hash=14695981039346656037ULL;
    if(validate){
      Strips raw(true);
      for(auto&jpeg:frames){
        decoder.Decode(dst,jpeg,PackAvx2);raw.Decode(reference,PackAvx2,jpeg.data(),jpeg.size());Check(dst==reference,"Stock planar/raw fast NV12 mismatch");
        decoder.Decode(reference,jpeg,PackScalar);Check(dst==reference,"Scalar/AVX2 mismatch");hash=Hash(hash,dst);
      }
      const int yp=width+13,up=width+29;std::vector<unsigned char> y(yp*height,0xa5),uv(up*height/2,0xa5);
      decoder.Decode(dst,frames[0],PackAvx2);decoder.Planes(y.data(),yp,frames[0]);decoder.Pack(uv.data(),up,PackAvx2);
      for(int row=0;row<height;row++){Check(std::memcmp(y.data()+row*yp,dst.data()+row*width,width)==0,"Padded Y mismatch");for(int x=width;x<yp;x++)Check(y[row*yp+x]==0xa5,"Y padding");}
      for(int row=0;row<height/2;row++){Check(std::memcmp(uv.data()+row*up,dst.data()+width*height+row*width,width)==0,"Padded UV mismatch");for(int x=width;x<up;x++)Check(uv[row*up+x]==0xa5,"UV padding");}
      std::printf("{\"frames\":%zu,\"fastdct\":1,\"avx2\":true,\"raw_fast_match\":true,\"scalar_pack_match\":true,\"strided_output\":true,\"hash\":\"%016llx\"}\n",frames.size(),(unsigned long long)hash);return 0;
    }
    std::vector<double> times,decode,packing;
    for(int pass=-1;pass<passes;pass++)for(auto&jpeg:frames){
      auto a=std::chrono::steady_clock::now();decoder.Planes(dst.data(),width,jpeg);auto b=std::chrono::steady_clock::now();
      decoder.Pack(dst.data()+width*height,width,PackAvx2);auto c=std::chrono::steady_clock::now();
      if(pass<0)hash=Hash(hash,dst);else{
        times.push_back(std::chrono::duration<double,std::milli>(c-a).count());
        decode.push_back(std::chrono::duration<double,std::milli>(b-a).count());packing.push_back(std::chrono::duration<double,std::milli>(c-b).count());
      }
    }
    auto mean=[](const std::vector<double>&v){double s=0;for(double x:v)s+=x;return s/v.size();};
    double total=mean(times);std::sort(times.begin(),times.end());
    std::printf("{\"frames\":%zu,\"passes\":%d,\"mean_ms\":%.9f,\"median_ms\":%.9f,\"decode_ms\":%.9f,\"pack_ms\":%.9f,\"hash\":\"%016llx\"}\n",frames.size(),passes,total,times[times.size()/2],mean(decode),mean(packing),(unsigned long long)hash);
  }catch(const std::exception&e){std::fprintf(stderr,"%s\n",e.what());return 1;}
}
