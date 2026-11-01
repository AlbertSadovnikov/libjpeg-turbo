// NV12-only validation and sequence timing for the isolated fused kernels.
#include <cstdio>
#include <cstddef>
#define JPEG_INTERNALS
#include "jpeglib.h"
#include "fusion.h"
int mjpeg_requested_mode=0;
#define main original_nv12_main
#include MJPEG_FUSED_PROTOTYPE
#undef main
#include <chrono>
#include <fstream>
#include <iterator>
#include <cstdint>

struct Delta {
  unsigned long long n=0,changed=0,absolute=0,squared=0;long long signed_sum=0;int peak=0;
  void Add(const unsigned char *a,const unsigned char *b,size_t count){
    n+=count;for(size_t i=0;i<count;i++){int d=int(a[i])-int(b[i]);changed+=d!=0;absolute+=std::abs(d);squared+=d*d;signed_sum+=d;peak=std::max(peak,std::abs(d));}
  }
  void Print() const {
    std::printf("{\"max_abs\":%d,\"mean_abs\":%.9f,\"mean_signed\":%.9f,\"changed_percent\":%.6f,\"mse\":%.9f}",peak,double(absolute)/n,double(signed_sum)/n,100.*changed/n,double(squared)/n);
  }
};
static uint64_t Hash(uint64_t hash,const std::vector<unsigned char>&v){for(auto x:v){hash^=x;hash*=1099511628211ULL;}return hash;}
int main(int argc,char **argv) {
  if(argc<3)return 2;
  width=1920;height=1080;subsamp=TJSAMP_422;
  bool validate=std::string(argv[1])=="validate";
  int first=validate?2:4;if(argc<=first)return 2;
  try {
    std::vector<std::vector<unsigned char>> frames;
    for(int i=first;i<argc;i++) {
      std::ifstream input(argv[i],std::ios::binary);Check(bool(input),"Frame read");
      frames.emplace_back(std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>());
    }
    auto pack=SimdPack();std::vector<unsigned char> a(width*height*3/2),b(a.size()),accurate(a.size());
    if(validate) {
      std::printf("{\"frames\":%zu,\"cases\":[",frames.size());bool comma=false;
      for(bool fast:{false,true})for(int mode:{1,2}) {
        Strips ref(fast),candidate(fast),acc(false);Delta y,uv,uv_acc;
        uint64_t href=14695981039346656037ULL,hout=href;
        for(const auto &jpeg:frames) {
          mjpeg_requested_mode=0;ref.Decode(a,pack,jpeg.data(),jpeg.size());
          if(fast)acc.Decode(accurate,pack,jpeg.data(),jpeg.size());else accurate=a;
          mjpeg_requested_mode=mode;candidate.Decode(b,pack,jpeg.data(),jpeg.size());
          y.Add(b.data(),a.data(),width*height);
          uv.Add(b.data()+width*height,a.data()+width*height,width*height/2);
          uv_acc.Add(b.data()+width*height,accurate.data()+width*height,width*height/2);
          href=Hash(href,a);hout=Hash(hout,b);
          Check(std::memcmp(a.data(),b.data(),width*height)==0,"Fusion changed luma");
          if(mode==1)Check(a==b,"Exact fusion mismatch");
        }
        // Unaligned padded destinations, checked on the first capture frame.
        const int yp=width+13,up=width+29;
        std::vector<unsigned char> py(yp*height,0xa5),pu(up*height/2,0xa5);
        mjpeg_requested_mode=mode;candidate.Decode(b,pack,frames[0].data(),frames[0].size());
        candidate.Decode(py.data(),yp,pu.data(),up,pack,frames[0].data(),frames[0].size());
        for(int row=0;row<height;row++){
          Check(std::memcmp(py.data()+row*yp,b.data()+row*width,width)==0,"Strided Y mismatch");
          for(int x=width;x<yp;x++)Check(py[row*yp+x]==0xa5,"Y padding overwritten");
        }
        for(int row=0;row<height/2;row++){
          Check(std::memcmp(pu.data()+row*up,b.data()+width*height+row*width,width)==0,"Strided UV mismatch");
          for(int x=width;x<up;x++)Check(pu[row*up+x]==0xa5,"UV padding overwritten");
        }
        std::printf("%s{\"idct\":\"%s\",\"mode\":%d,\"reference_hash\":\"%016llx\",\"output_hash\":\"%016llx\",\"Y\":",comma?",":"",fast?"fast":"accurate",mode,(unsigned long long)href,(unsigned long long)hout);comma=true;
        y.Print();std::printf(",\"UV_vs_same_idct\":");uv.Print();std::printf(",\"UV_vs_accurate\":");uv_acc.Print();std::printf("}");
      }
      std::printf("]}\n");return 0;
    }
    bool fast=std::string(argv[1])=="fast";int mode=std::atoi(argv[2]),passes=std::atoi(argv[3]);Check(passes>0,"Pass count");
    mjpeg_requested_mode=mode;Strips decoder(fast);std::vector<double> times;uint64_t hash=14695981039346656037ULL;
    for(int pass=-1;pass<passes;pass++)for(const auto &jpeg:frames) {
      auto start=std::chrono::steady_clock::now();decoder.Decode(b,pack,jpeg.data(),jpeg.size());auto end=std::chrono::steady_clock::now();
      if(pass<0)hash=Hash(hash,b);else times.push_back(std::chrono::duration<double,std::milli>(end-start).count());
    }
    double total=0;for(double x:times)total+=x;std::sort(times.begin(),times.end());
    std::printf("{\"frames\":%zu,\"passes\":%d,\"mean_ms\":%.9f,\"median_ms\":%.9f,\"hash\":\"%016llx\"}\n",frames.size(),passes,total/times.size(),times[times.size()/2],(unsigned long long)hash);
  }catch(const std::exception&e){std::fprintf(stderr,"%s\n",e.what());return 1;}
}
