// Benchmarks use the compiled-in JPEG exclusively. No frame is read at runtime.
#include <benchmark/benchmark.h>

#include <array>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <exception>
#include <stdexcept>
#include <string>
#include <vector>

#include "jconfigint.h"
#define JPEG_INTERNALS
#include "jpeglib.h"
#include "turbojpeg.h"
#include "embedded_frame.h"
#include "huffman_tables.h"

namespace {
using mjpeg_bench::kJpeg;
using mjpeg_bench::kJpegSize;

void Require(bool condition, const char *message)
{
  if (!condition) throw std::runtime_error(message);
}

struct FrameInfo {
  int width = 0, height = 0, subsamp = 0;
} frame;
bool benchmark_failed = false;

struct Options {
  int format = TJPF_BGR;
  J_COLOR_SPACE color = JCS_EXT_BGR;
  int scale = 1;
  bool fast_upsample = false, fast_idct = false;
};

class Decoder {
 public:
  jpeg_decompress_struct c{};
  jpeg_error_mgr error{};

  Decoder()
  {
    c.err = jpeg_std_error(&error);
    jpeg_create_decompress(&c);
  }
  ~Decoder() { jpeg_destroy_decompress(&c); }
  Decoder(const Decoder &) = delete;
  Decoder &operator=(const Decoder &) = delete;

  void Header()
  {
    jpeg_mem_src(&c, kJpeg, static_cast<unsigned long>(kJpegSize));
    Require(jpeg_read_header(&c, TRUE) == JPEG_HEADER_OK, "Incomplete JPEG header");
  }
  void Start(const Options &options = {})
  {
    c.out_color_space = options.color;
    c.scale_num = 1;
    c.scale_denom = options.scale;
    c.do_fancy_upsampling = !options.fast_upsample;
    c.dct_method = options.fast_idct ? JDCT_IFAST : JDCT_ISLOW;
    Require(jpeg_start_decompress(&c), "Unexpected input suspension");
  }
  void Finish()
  {
    Require(jpeg_finish_decompress(&c), "Unexpected input suspension");
    Require(error.num_warnings == 0, "JPEG decoder warning");
  }
  void Abort() { jpeg_abort_decompress(&c); }
};

struct Output {
  int width, height, pitch;
  std::vector<unsigned char> pixels;
  std::vector<JSAMPROW> rows;

  explicit Output(const Options &options = {})
    : width((frame.width + options.scale - 1) / options.scale),
      height((frame.height + options.scale - 1) / options.scale),
      pitch(width * tjPixelSize[options.format]),
      pixels(static_cast<std::size_t>(pitch) * height), rows(height)
  {
    for (int y = 0; y < height; ++y)
      rows[y] = pixels.data() + static_cast<std::size_t>(y) * pitch;
  }
};

void Decode(Decoder &decoder, Output &output, const Options &options = {})
{
  decoder.Header();
  decoder.Start(options);
  auto &c = decoder.c;
  Require(c.output_width == static_cast<JDIMENSION>(output.width) &&
          c.output_height == static_cast<JDIMENSION>(output.height) &&
          c.output_components == tjPixelSize[options.format],
          "Unexpected output geometry");
  while (c.output_scanline < c.output_height)
    Require(jpeg_read_scanlines(&c, output.rows.data() + c.output_scanline,
                                c.output_height - c.output_scanline) != 0,
            "Unexpected input suspension");
  decoder.Finish();
}

class TurboDecoder {
 public:
  tjhandle handle;
  TurboDecoder() : handle(tj3Init(TJINIT_DECOMPRESS))
  {
    Require(handle != nullptr, "Unable to create TurboJPEG decompressor");
  }
  ~TurboDecoder() { tj3Destroy(handle); }
  TurboDecoder(const TurboDecoder &) = delete;
  TurboDecoder &operator=(const TurboDecoder &) = delete;
  void Check(int result)
  {
    if (result < 0) throw std::runtime_error(tj3GetErrorStr(handle));
  }
  void Configure(const Options &options)
  {
    Check(tj3Set(handle, TJPARAM_FASTUPSAMPLE, options.fast_upsample));
    Check(tj3Set(handle, TJPARAM_FASTDCT, options.fast_idct));
    Check(tj3SetScalingFactor(handle, tjscalingfactor{1, options.scale}));
  }
  void DecodeTo(Output &output, const Options &options)
  {
    Check(tj3Decompress8(handle, kJpeg, kJpegSize, output.pixels.data(),
                        output.pitch, options.format));
  }
};

void FrameCounters(benchmark::State &state, int scale = 1, bool compressed_input = true)
{
  state.SetItemsProcessed(state.iterations());
  if (compressed_input)
    state.SetBytesProcessed(state.iterations() * static_cast<std::int64_t>(kJpegSize));
  const double pixels = static_cast<double>((frame.width + scale - 1) / scale) *
                        ((frame.height + scale - 1) / scale);
  state.counters["MPix/s"] = benchmark::Counter(
    state.iterations() * pixels / 1e6, benchmark::Counter::kIsRate);
}

void LibjpegDecode(benchmark::State &state, Options options, bool fresh)
{
  Output output(options);
  Decoder reused;
  Decode(reused, output, options);  // Fault in output pages and warm the decoder.
  for (auto _ : state) {
    if (fresh) {
      Decoder decoder;
      Decode(decoder, output, options);
    } else {
      Decode(reused, output, options);
    }
    benchmark::ClobberMemory();
  }
  FrameCounters(state, options.scale);
}

void TurboDecode(benchmark::State &state, Options options, bool fresh)
{
  Output output(options);
  TurboDecoder reused;
  reused.Configure(options);
  reused.DecodeTo(output, options);
  for (auto _ : state) {
    if (fresh) {
      TurboDecoder decoder;
      decoder.Configure(options);
      decoder.DecodeTo(output, options);
    } else {
      reused.DecodeTo(output, options);
    }
    benchmark::ClobberMemory();
  }
  FrameCounters(state, options.scale);
}

void HeaderAndAbort(benchmark::State &state)
{
  Decoder decoder;
  for (auto _ : state) {
    decoder.Header();
    benchmark::DoNotOptimize(decoder.c.image_width);
    decoder.Abort();
  }
  state.SetItemsProcessed(state.iterations());
}

void CreateDestroy(benchmark::State &state)
{
  for (auto _ : state) {
    Decoder decoder;
    benchmark::DoNotOptimize(&decoder.c);
  }
  state.SetItemsProcessed(state.iterations());
}

void Startup(benchmark::State &state)
{
  Decoder decoder;
  for (auto _ : state) {
    state.PauseTiming();
    decoder.Header();
    state.ResumeTiming();
    decoder.Start();
    benchmark::ClobberMemory();
    state.PauseTiming();
    decoder.Abort();
    state.ResumeTiming();
  }
  state.SetItemsProcessed(state.iterations());
}

void DerivedHuffmanTables(benchmark::State &state)
{
  Decoder decoder;
  decoder.Header();
  // The C shim keeps jdhuff.h's C-only declarations out of C++17 code.
  auto tables = mjpeg_bench_create_huffman_tables(&decoder.c);
  for (auto _ : state) {
    mjpeg_bench_rebuild_huffman_tables(&decoder.c, tables);
    benchmark::ClobberMemory();
  }
  state.SetItemsProcessed(state.iterations());
}

struct alignas(32) Block { JCOEF values[DCTSIZE2]; };
struct CoefficientPlane {
  JDIMENSION width, height;
  std::vector<Block> blocks;
};
struct Coefficients {
  std::vector<CoefficientPlane> planes;
  Coefficients()
  {
    Decoder decoder;
    decoder.Header();
    auto arrays = jpeg_read_coefficients(&decoder.c);
    Require(arrays != nullptr, "Unable to read frame coefficients");
    planes.resize(decoder.c.num_components);
    for (int ci = 0; ci < decoder.c.num_components; ++ci) {
      auto &plane = planes[ci];
      auto &component = decoder.c.comp_info[ci];
      plane.width = component.width_in_blocks;
      plane.height = component.height_in_blocks;
      plane.blocks.resize(static_cast<std::size_t>(plane.width) * plane.height);
      for (JDIMENSION y = 0; y < plane.height; ++y) {
        auto row = decoder.c.mem->access_virt_barray(
          reinterpret_cast<j_common_ptr>(&decoder.c), arrays[ci], y, 1, FALSE);
        for (JDIMENSION x = 0; x < plane.width; ++x)
          std::memcpy(plane.blocks[static_cast<std::size_t>(y) * plane.width + x].values,
                      row[0][x], sizeof(JBLOCK));
      }
    }
    decoder.Finish();
  }
};

Coefficients &FrameCoefficients()
{
  static Coefficients coefficients;
  return coefficients;
}

void ReadCoefficients(benchmark::State &state)
{
  Decoder decoder;
  for (auto _ : state) {
    decoder.Header();
    auto arrays = jpeg_read_coefficients(&decoder.c);
    Require(arrays != nullptr, "Unable to read frame coefficients");
    benchmark::DoNotOptimize(arrays);
    decoder.Finish();
  }
  FrameCounters(state);
}

template<bool Store>
void EntropyPass(Decoder &decoder, const Coefficients *verify = nullptr)
{
  auto &c = decoder.c;
  alignas(32) JBLOCK blocks[D_MAX_BLOCKS_IN_MCU];
  JBLOCKROW pointers[D_MAX_BLOCKS_IN_MCU];
  for (int i = 0; i < c.blocks_in_MCU; ++i) pointers[i] = &blocks[i];
  for (JDIMENSION my = 0; my < c.MCU_rows_in_scan; ++my) {
    for (JDIMENSION mx = 0; mx < c.MCUs_per_row; ++mx) {
      if constexpr (Store)
        std::memset(blocks, 0, static_cast<std::size_t>(c.blocks_in_MCU) * sizeof(JBLOCK));
      Require(c.entropy->decode_mcu(&c, Store ? pointers : nullptr),
              "Entropy decoder suspended");
      if (verify) {
        int block = 0;
        for (int ci = 0; ci < c.comps_in_scan; ++ci) {
          const auto &component = *c.cur_comp_info[ci];
          const auto &plane = verify->planes[component.component_index];
          for (int y = 0; y < component.MCU_height; ++y) {
            for (int x = 0; x < component.MCU_width; ++x, ++block) {
              const JDIMENSION py = my * component.MCU_height + y;
              const JDIMENSION px = mx * component.MCU_width + x;
              if (py < plane.height && px < plane.width)
                Require(std::memcmp(blocks[block],
                        plane.blocks[static_cast<std::size_t>(py) * plane.width + px].values,
                        sizeof(JBLOCK)) == 0, "Entropy coefficient mismatch");
            }
          }
        }
      }
    }
  }
  Require(decoder.error.num_warnings == 0, "Entropy decoder warning");
}

template<bool Store>
void Entropy(benchmark::State &state)
{
  Decoder decoder;
  for (auto _ : state) {
    state.PauseTiming();
    decoder.Header();
    decoder.Start();
    state.ResumeTiming();
    EntropyPass<Store>(decoder);
    benchmark::ClobberMemory();
    state.PauseTiming();
    decoder.Abort();
    state.ResumeTiming();
  }
  FrameCounters(state);
}

struct PlanarOutput {
  std::vector<std::vector<unsigned char>> pixels;
  std::vector<std::vector<JSAMPROW>> rows;
  explicit PlanarOutput(const Coefficients &coefficients)
    : pixels(coefficients.planes.size()), rows(coefficients.planes.size())
  {
    for (std::size_t ci = 0; ci < pixels.size(); ++ci) {
      const auto &plane = coefficients.planes[ci];
      const std::size_t width = plane.width * DCTSIZE;
      const std::size_t height = plane.height * DCTSIZE;
      pixels[ci].resize(width * height);
      rows[ci].resize(height);
      for (std::size_t y = 0; y < height; ++y)
        rows[ci][y] = pixels[ci].data() + y * width;
    }
  }
};

void IdctPass(Decoder &decoder, Coefficients &coefficients, PlanarOutput &output)
{
  for (int ci = 0; ci < decoder.c.num_components; ++ci) {
    auto &plane = coefficients.planes[ci];
    auto method = decoder.c.idct->inverse_DCT[ci];
    for (JDIMENSION y = 0; y < plane.height; ++y)
      for (JDIMENSION x = 0; x < plane.width; ++x)
        method(&decoder.c, &decoder.c.comp_info[ci],
               plane.blocks[static_cast<std::size_t>(y) * plane.width + x].values,
               output.rows[ci].data() + y * DCTSIZE, x * DCTSIZE);
  }
}

void Idct(benchmark::State &state, bool fast)
{
  auto &coefficients = FrameCoefficients();
  PlanarOutput output(coefficients);
  Decoder decoder;
  decoder.Header();
  Options options;
  options.fast_idct = fast;
  decoder.Start(options);
  for (auto _ : state) {
    IdctPass(decoder, coefficients, output);
    benchmark::ClobberMemory();
  }
  FrameCounters(state, 1, false);
}

std::vector<unsigned char> YuvBuffer()
{
  const auto size = tj3YUVBufSize(frame.width, 1, frame.height, frame.subsamp);
  Require(size != 0, "Invalid planar YUV buffer size");
  return std::vector<unsigned char>(size);
}

void DecompressToYuv(benchmark::State &state)
{
  TurboDecoder decoder;
  auto yuv = YuvBuffer();
  for (auto _ : state) {
    decoder.Check(tj3DecompressToYUV8(decoder.handle, kJpeg, kJpegSize, yuv.data(), 1));
    benchmark::ClobberMemory();
  }
  FrameCounters(state);
}

void YuvToBgr(benchmark::State &state)
{
  TurboDecoder decoder;
  auto yuv = YuvBuffer();
  decoder.Check(tj3DecompressToYUV8(decoder.handle, kJpeg, kJpegSize, yuv.data(), 1));
  Output output;
  for (auto _ : state) {
    decoder.Check(tj3DecodeYUV8(decoder.handle, yuv.data(), 1, output.pixels.data(),
                               frame.width, output.pitch, frame.height, TJPF_BGR));
    benchmark::ClobberMemory();
  }
  FrameCounters(state, 1, false);
}

struct FullResolutionYCbCr {
  std::array<std::vector<unsigned char>, 3> pixels;
  std::array<std::vector<JSAMPROW>, 3> rows;

  FullResolutionYCbCr()
  {
    Options options;
    options.color = JCS_YCbCr;
    Output interleaved(options);
    Decoder decoder;
    Decode(decoder, interleaved, options);
    const std::size_t samples = static_cast<std::size_t>(frame.width) * frame.height;
    for (int ci = 0; ci < 3; ++ci) {
      pixels[ci].resize(samples);
      rows[ci].resize(frame.height);
      for (std::size_t i = 0; i < samples; ++i)
        pixels[ci][i] = interleaved.pixels[3 * i + ci];
      for (int y = 0; y < frame.height; ++y)
        rows[ci][y] = pixels[ci].data() + static_cast<std::size_t>(y) * frame.width;
    }
  }
};

void ColorPass(Decoder &decoder, FullResolutionYCbCr &input, Output &output)
{
  JSAMPARRAY planes[3] = {input.rows[0].data(), input.rows[1].data(),
                         input.rows[2].data()};
  decoder.c.cconvert->color_convert(&decoder.c, planes, 0, output.rows.data(),
                                    frame.height);
}

void ColorOnly(benchmark::State &state)
{
  FullResolutionYCbCr input;
  Output output;
  Decoder decoder;
  decoder.Header();
  decoder.Start();
  for (auto _ : state) {
    ColorPass(decoder, input, output);
    benchmark::ClobberMemory();
  }
  FrameCounters(state, 1, false);
}

// Validate stage plumbing against complete library decodes before timing.
void ValidateFrame()
{
  Decoder decoder;
  decoder.Header();
  auto &c = decoder.c;
  Require(c.data_precision == 8 && !c.progressive_mode && !c.arith_code &&
          c.jpeg_color_space == JCS_YCbCr && c.num_components == 3 &&
          c.comps_in_scan == 3 && c.restart_interval == 0,
          "Stage benchmarks require interleaved 8-bit sequential YCbCr JPEG without restart intervals");
  frame.width = static_cast<int>(c.image_width);
  frame.height = static_cast<int>(c.image_height);
  decoder.Abort();
  TurboDecoder turbo;
  turbo.Check(tj3DecompressHeader(turbo.handle, kJpeg, kJpegSize));
  frame.subsamp = tj3Get(turbo.handle, TJPARAM_SUBSAMP);
  Require(frame.subsamp >= 0, "Unsupported chroma subsampling");
  Output expected, actual;
  Decode(decoder, expected);
  turbo.DecodeTo(actual, {});
  Require(actual.pixels == expected.pixels, "libjpeg/TurboJPEG pixel mismatch");
  auto &coefficients = FrameCoefficients();
  decoder.Header();
  decoder.Start();
  EntropyPass<true>(decoder, &coefficients);
  decoder.Abort();
  auto yuv = YuvBuffer();
  turbo.Check(tj3DecompressToYUV8(turbo.handle, kJpeg, kJpegSize, yuv.data(), 1));
  turbo.Check(tj3DecodeYUV8(turbo.handle, yuv.data(), 1, actual.pixels.data(),
                           frame.width, actual.pitch, frame.height, TJPF_BGR));
  Options fast_upsample;
  fast_upsample.fast_upsample = true;
  Output fast_reference(fast_upsample);
  Decode(decoder, fast_reference, fast_upsample);
  Require(actual.pixels == fast_reference.pixels, "Planar YUV conversion pixel mismatch");
  FullResolutionYCbCr color_input;
  decoder.Header();
  decoder.Start();
  ColorPass(decoder, color_input, actual);
  Require(actual.pixels == expected.pixels, "Color conversion pixel mismatch");
  decoder.Abort();
  for (bool fast : {false, true}) {
    Options options;
    options.fast_idct = fast;
    decoder.Header();
    decoder.Start(options);
    PlanarOutput idct(coefficients), reference(coefficients);
    IdctPass(decoder, coefficients, idct);
    unsigned char *planes[MAX_COMPONENTS] = {};
    int strides[MAX_COMPONENTS] = {};
    for (std::size_t ci = 0; ci < coefficients.planes.size(); ++ci) {
      planes[ci] = reference.pixels[ci].data();
      strides[ci] = static_cast<int>(coefficients.planes[ci].width * DCTSIZE);
    }
    turbo.Configure(options);
    turbo.Check(tj3DecompressToYUVPlanes8(turbo.handle, kJpeg, kJpegSize, planes, strides));
    for (int ci = 0; ci < decoder.c.num_components; ++ci) {
      const auto &component = decoder.c.comp_info[ci];
      for (JDIMENSION y = 0; y < component.downsampled_height; ++y)
        Require(std::memcmp(idct.rows[ci][y], reference.rows[ci][y],
                            component.downsampled_width) == 0, "IDCT plane mismatch");
    }
    decoder.Abort();
  }
}

template<class Function>
void Register(const std::string &name, Function function,
              benchmark::TimeUnit unit = benchmark::kMillisecond)
{
  benchmark::RegisterBenchmark(name.c_str(), [function](benchmark::State &state) {
    try {
      function(state);
    } catch (const std::exception &error) {
      benchmark_failed = true;
      state.SkipWithError(error.what());
    }
  })->Unit(unit);
}

void RegisterBenchmarks()
{
  const auto full = [](const char *name, const Options &options) {
    Register(std::string("MJPEG/Libjpeg/") + name,
             [options](benchmark::State &s) { LibjpegDecode(s, options, false); });
    Register(std::string("MJPEG/TurboJPEG/") + name,
             [options](benchmark::State &s) { TurboDecode(s, options, false); });
  };
  Options options;
  full("BGR_Reused", options);
  Register("MJPEG/Libjpeg/BGR_FreshDecoder",
           [](benchmark::State &s) { LibjpegDecode(s, {}, true); });
  Register("MJPEG/TurboJPEG/BGR_FreshDecoder",
           [](benchmark::State &s) { TurboDecode(s, {}, true); });
  options.fast_upsample = true;
  full("BGR_FastUpsample", options);
  options = {};
  options.fast_idct = true;
  full("BGR_FastIDCT", options);
  options.fast_upsample = true;
  full("BGR_FastBoth", options);
  options = {};
  options.color = JCS_GRAYSCALE;
  options.format = TJPF_GRAY;
  full("Gray", options);
  options = {};
  options.color = JCS_EXT_BGRA;
  options.format = TJPF_BGRA;
  full("BGRA", options);
  for (int scale : {2, 4, 8}) {
    options = {};
    options.scale = scale;
    const std::string name = "BGR_Scale1_" + std::to_string(scale);
    full(name.c_str(), options);
  }
  Register("MJPEG/Libjpeg/CreateDestroy", CreateDestroy, benchmark::kMicrosecond);
  Register("MJPEG/Libjpeg/HeaderAndAbort", HeaderAndAbort, benchmark::kMicrosecond);
  Register("MJPEG/Stages/Startup", Startup, benchmark::kMicrosecond);
  Register("MJPEG/Stages/DerivedHuffmanTables_ReusedStorage", DerivedHuffmanTables,
           benchmark::kMicrosecond);
  Register("MJPEG/Libjpeg/ReadCoefficients", ReadCoefficients);
  Register("MJPEG/Stages/EntropyWithStoresAndZeroing", Entropy<true>);
  Register("MJPEG/Stages/EntropyDiscardCoefficients", Entropy<false>);
  Register("MJPEG/Stages/IDCT_Accurate", [](benchmark::State &s) { Idct(s, false); });
  Register("MJPEG/Stages/IDCT_Fast", [](benchmark::State &s) { Idct(s, true); });
  Register("MJPEG/TurboJPEG/DecompressToPlanarYUV", DecompressToYuv);
  Register("MJPEG/Stages/YUVToBGR_BoxUpsample", YuvToBgr);
  Register("MJPEG/Stages/ColorOnly_YCbCrToBGR", ColorOnly);
}
}  // namespace

int main(int argc, char **argv)
{
  benchmark::Initialize(&argc, argv);
  if (benchmark::ReportUnrecognizedArguments(argc, argv)) return 1;
  try {
    ValidateFrame();
    benchmark::AddCustomContext("jpeg_sha256", MJPEG_FRAME_SHA256);
    benchmark::AddCustomContext("jpeg_bytes", std::to_string(kJpegSize));
    benchmark::AddCustomContext("image", std::to_string(frame.width) + "x" +
                                        std::to_string(frame.height));
    benchmark::AddCustomContext("input", "compiled-in JPEG; no runtime frame loading");
    RegisterBenchmarks();
    benchmark::RunSpecifiedBenchmarks();
  } catch (const std::exception &error) {
    std::fprintf(stderr, "Embedded frame validation failed: %s\n", error.what());
    return 1;
  }
  benchmark::Shutdown();
  return benchmark_failed ? 1 : 0;
}
