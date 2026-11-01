// Preload the capture; time only full JPEG->NV12 decode, never disk reads/hash.
#define main nv12_google_benchmark_main
#include "../../../benchmarks/nv12_bench.cc"
#undef main
#include <chrono>
#include <fstream>
#include <iterator>

int main(int argc,char **argv)
{
  if(argc<5 || (std::string(argv[1])!="accurate" && std::string(argv[1])!="fast")) return 2;
  int passes=std::atoi(argv[2]); if(passes<1) return 2;
  width=1920; height=1080; subsamp=TJSAMP_422;
  try {
    std::vector<std::vector<unsigned char>> frames;
    for(int i=3;i<argc;i++) {
      std::ifstream input(argv[i],std::ios::binary); Check(bool(input),"Read frame");
      frames.emplace_back(std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>());
      Check(!frames.back().empty(),"Empty frame");
    }
    Strips decoder(std::string(argv[1])=="fast");
    std::vector<unsigned char> dst(width*height*3/2);
    std::vector<double> times; times.reserve(passes*frames.size());
    unsigned long long hash=14695981039346656037ULL;
    auto pack=SimdPack();
    for(int pass=-1;pass<passes;pass++) {
      for(const auto &jpeg:frames) {
        auto start=std::chrono::steady_clock::now();
        decoder.Decode(dst,pack,jpeg.data(),jpeg.size());
        auto finish=std::chrono::steady_clock::now();
        if(pass<0) {
          for(auto x:dst) { hash^=x; hash*=1099511628211ULL; }
        } else times.push_back(std::chrono::duration<double,std::milli>(finish-start).count());
      }
    }
    double total=0; for(double x:times) total+=x;
    std::sort(times.begin(),times.end());
    std::printf("{\"frames\":%zu,\"passes\":%d,\"mean_ms\":%.6f,\"median_ms\":%.6f,\"hash\":\"%016llx\"}\n",
                frames.size(),passes,total/times.size(),times[times.size()/2],hash);
  } catch(const std::exception &e) { std::fprintf(stderr,"%s\n",e.what()); return 1; }
}
