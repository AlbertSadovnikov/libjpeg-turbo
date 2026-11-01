// Reuse the validated NV12 prototype without Google Benchmark calibration.
// This is an experiment driver, not a public codec API.
#define main nv12_google_benchmark_main
#include "../../../benchmarks/nv12_bench.cc"
#undef main
#include <chrono>
#include <fstream>

int main(int argc,char **argv)
{
  if(argc!=3 || (std::string(argv[1])!="accurate" && std::string(argv[1])!="fast")) return 2;
  int frames=std::atoi(argv[2]); if(frames<1) return 2;
  width=1920; height=1080; subsamp=TJSAMP_422;
  try {
    std::ofstream control; std::ifstream acknowledgement;
    const char *path=std::getenv("MJPEG_PERF_CONTROL");
    if(path) { control.open(path); acknowledgement.open(std::string(path)+".ack"); }
    auto command=[&](const char *cmd) {
      if(!path) return;
      control << cmd << '\n' << std::flush;
      std::string ack;
      Check(bool(std::getline(acknowledgement,ack)),"perf acknowledgement");
      ack.erase(std::remove(ack.begin(),ack.end(),'\0'),ack.end());
      Check(ack=="ack","perf acknowledgement contents");
    };
    Strips decoder(std::string(argv[1])=="fast");
    std::vector<unsigned char> dst(width*height*3/2);
    auto pack=SimdPack();
    for(int i=0;i<5;i++) decoder.Decode(dst,pack);
    std::vector<double> timings; timings.reserve(frames);
    for(int i=0;i<frames;i++) {
      auto start=std::chrono::steady_clock::now(); command("enable");
      decoder.Decode(dst,pack);
      command("disable"); auto finish=std::chrono::steady_clock::now();
      timings.push_back(std::chrono::duration<double,std::milli>(finish-start).count());
    }
    unsigned long long hash=14695981039346656037ULL;
    for(auto x:dst) { hash^=x; hash*=1099511628211ULL; }
    std::sort(timings.begin(),timings.end());
    std::printf("{\"median_ms\":%.6f,\"hash\":\"%016llx\"}\n",timings[frames/2],hash);
  } catch(const std::exception &e) { std::fprintf(stderr,"%s\n",e.what()); return 1; }
}
