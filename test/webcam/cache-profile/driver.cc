// Embedded-frame profiling driver. Collection excludes setup and disturbance.
#include <valgrind/callgrind.h>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>
#include <fstream>
#include "jconfigint.h"
#define JPEG_INTERNALS
#include "jpeglib.h"
#include "embedded_frame.h"

class Driver {
 public:
  jpeg_decompress_struct c{};
  jpeg_error_mgr error{};
  std::vector<unsigned char> pixels;
  std::vector<JSAMPROW> rows;
  std::vector<unsigned char> disturbance;
  alignas(32) JBLOCK blocks[D_MAX_BLOCKS_IN_MCU];
  JBLOCKROW pointers[D_MAX_BLOCKS_IN_MCU];

  explicit Driver(std::size_t kib) : disturbance(kib*1024)
  {
    c.err=jpeg_std_error(&error);
    jpeg_create_decompress(&c);
    Header();
    pixels.resize(static_cast<std::size_t>(c.image_width)*c.image_height*3);
    rows.resize(c.image_height);
    for (JDIMENSION y=0;y<c.image_height;++y)
      rows[y]=pixels.data()+static_cast<std::size_t>(y)*c.image_width*3;
    for (int i=0;i<D_MAX_BLOCKS_IN_MCU;++i) pointers[i]=&blocks[i];
    jpeg_abort_decompress(&c);
  }
  ~Driver() { jpeg_destroy_decompress(&c); }
  void Header()
  {
    jpeg_mem_src(&c,mjpeg_bench::kJpeg,mjpeg_bench::kJpegSize);
    if(jpeg_read_header(&c,TRUE)!=JPEG_HEADER_OK) throw std::runtime_error("header");
  }
  void Start()
  {
    c.out_color_space=JCS_EXT_BGR;
    c.dct_method=JDCT_ISLOW;
    c.do_fancy_upsampling=TRUE;
    if(!jpeg_start_decompress(&c)) throw std::runtime_error("start");
  }
  void Disturb()
  {
    // Touch every line outside the measured/collected region. This creates
    // controlled competing data; it is not a hardware cache-flush guarantee.
    volatile unsigned char *p=disturbance.data();
    for(std::size_t i=0;i<disturbance.size();i+=64) p[i]^=1;
  }
  void Full()
  {
    Header(); Start();
    while(c.output_scanline<c.output_height)
      if(!jpeg_read_scanlines(&c,rows.data()+c.output_scanline,
                              c.output_height-c.output_scanline))
        throw std::runtime_error("scanlines");
    if(!jpeg_finish_decompress(&c)) throw std::runtime_error("finish");
  }
  void Entropy()
  {
    const std::size_t mcus=static_cast<std::size_t>(c.MCUs_per_row)*c.MCU_rows_in_scan;
    for(std::size_t m=0;m<mcus;++m) {
      std::memset(blocks,0,static_cast<std::size_t>(c.blocks_in_MCU)*sizeof(JBLOCK));
      if(!c.entropy->decode_mcu(&c,pointers)) throw std::runtime_error("entropy");
    }
  }
};

int main(int argc,char **argv)
{
  if(argc!=5) {
    std::fprintf(stderr,"usage: driver full|entropy measured_frames warmup_frames disturbance_KiB\n");
    return 2;
  }
  const bool entropy=std::string(argv[1])=="entropy";
  if(!entropy && std::string(argv[1])!="full") return 2;
  const int measured=std::atoi(argv[2]),warmup=std::atoi(argv[3]);
  const int kib=std::atoi(argv[4]);
  if(measured<1||warmup<1||kib<0) return 2;
  try {
    const char *perf_control=std::getenv("MJPEG_PERF_CONTROL");
    std::ofstream control;
    std::ifstream acknowledgement;
    if(perf_control) {
      control.open(perf_control);
      acknowledgement.open(std::string(perf_control)+".ack");
      if(!control || !acknowledgement) throw std::runtime_error("perf control open");
    }
    auto perf_command=[&](const char *command) {
      if(!perf_control) return;
      control << command << '\n' << std::flush;
      std::string ack;
      if(!std::getline(acknowledgement,ack))
        throw std::runtime_error("perf acknowledgement");
      ack.erase(std::remove(ack.begin(),ack.end(),'\0'),ack.end());
      if(ack!="ack") throw std::runtime_error("perf acknowledgement: "+ack);
    };
    Driver driver(static_cast<std::size_t>(kib));
    std::vector<double> timings;
    timings.reserve(measured);
    // Run Callgrind with --instr-atstart=no --collect-atstart=no. Instrumented
    // warmup updates its cache model while event aggregation remains off.
    CALLGRIND_START_INSTRUMENTATION;
    for(int i=-warmup;i<measured;++i) {
      if(entropy) { driver.Header(); driver.Start(); }
      driver.Disturb();
      const auto start=std::chrono::steady_clock::now();
      if(i>=0) perf_command("enable");
      if(i>=0) { CALLGRIND_TOGGLE_COLLECT; }
      if(entropy) driver.Entropy(); else driver.Full();
      if(i>=0) { CALLGRIND_TOGGLE_COLLECT; }
      if(i>=0) perf_command("disable");
      const auto finish=std::chrono::steady_clock::now();
      if(entropy) jpeg_abort_decompress(&driver.c);
      if(driver.error.num_warnings) throw std::runtime_error("decoder warning");
      if(i>=0) timings.push_back(std::chrono::duration<double,std::milli>(finish-start).count());
    }
    // Hash outside collection; native/profiled runs can check identical output.
    std::uint64_t hash=UINT64_C(14695981039346656037);
    const auto *bytes=entropy?reinterpret_cast<const unsigned char *>(driver.blocks):driver.pixels.data();
    const std::size_t size=entropy?static_cast<std::size_t>(driver.c.blocks_in_MCU)*sizeof(JBLOCK):driver.pixels.size();
    for(std::size_t i=0;i<size;++i) { hash^=bytes[i]; hash*=UINT64_C(1099511628211); }
    std::sort(timings.begin(),timings.end());
    double sum=0; for(double t:timings) sum+=t;
    std::printf("{\"mode\":\"%s\",\"frames\":%d,\"disturbance_kib\":%d,\"mean_ms\":%.6f,\"median_ms\":%.6f,\"hash\":\"%016llx\"}\n",
                entropy?"entropy":"full",measured,kib,sum/measured,
                timings[timings.size()/2],static_cast<unsigned long long>(hash));
  } catch(const std::exception &e) { std::fprintf(stderr,"%s\n",e.what()); return 1; }
  return 0;
}
