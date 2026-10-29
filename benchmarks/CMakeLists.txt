# Keep C++ and the dependency download out of ordinary C-only builds.
if(NOT ENABLE_STATIC OR NOT WITH_TURBOJPEG)
  message(FATAL_ERROR
    "WITH_BENCHMARKS requires ENABLE_STATIC=ON and WITH_TURBOJPEG=ON.")
endif()
enable_language(CXX)

include(FetchContent)
set(BENCHMARK_ENABLE_TESTING OFF CACHE BOOL "" FORCE)
set(BENCHMARK_ENABLE_GTEST_TESTS OFF CACHE BOOL "" FORCE)
set(BENCHMARK_ENABLE_INSTALL OFF CACHE BOOL "" FORCE)
set(BENCHMARK_ENABLE_WERROR OFF CACHE BOOL "" FORCE)
# Preserve fresh extraction timestamps with CMake >= 3.24.
if(POLICY CMP0135)
  cmake_policy(SET CMP0135 NEW)
endif()
FetchContent_Declare(googlebenchmark
  URL https://codeload.github.com/google/benchmark/tar.gz/refs/tags/v1.10.0
  DOWNLOAD_NAME google-benchmark-v1.10.0.tar.gz
  URL_HASH SHA256=acc5c7c0fbed855c4aaa2d7c3c36fb82b0c15c28f4e151e3f679c2fc0aa404af)
FetchContent_MakeAvailable(googlebenchmark)

set(MJPEG_BENCHMARK_FRAME
  "${CMAKE_CURRENT_SOURCE_DIR}/data/webcam_1920x1080_422.jpg"
  CACHE FILEPATH "Interleaved 8-bit baseline YCbCr JPEG to embed in mjpeg-bench")
get_filename_component(MJPEG_BENCHMARK_FRAME "${MJPEG_BENCHMARK_FRAME}"
  ABSOLUTE BASE_DIR "${CMAKE_SOURCE_DIR}")
if(NOT EXISTS "${MJPEG_BENCHMARK_FRAME}")
  message(FATAL_ERROR "MJPEG benchmark frame not found: ${MJPEG_BENCHMARK_FRAME}")
endif()
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
  "${MJPEG_BENCHMARK_FRAME}")
file(SHA256 "${MJPEG_BENCHMARK_FRAME}" MJPEG_FRAME_SHA256)
set(EMBEDDED_FRAME "${CMAKE_CURRENT_BINARY_DIR}/embedded_frame.cc")
add_custom_command(OUTPUT "${EMBEDDED_FRAME}"
  COMMAND ${CMAKE_COMMAND}
    "-DINPUT=${MJPEG_BENCHMARK_FRAME}" "-DOUTPUT=${EMBEDDED_FRAME}"
    -P "${CMAKE_CURRENT_SOURCE_DIR}/embed_frame.cmake"
  DEPENDS "${MJPEG_BENCHMARK_FRAME}"
    "${CMAKE_CURRENT_SOURCE_DIR}/embed_frame.cmake"
  COMMENT "Embedding the MJPEG frame in the benchmark executable"
  VERBATIM)

add_executable(mjpeg-bench mjpeg_bench.cc huffman_tables.c "${EMBEDDED_FRAME}")
target_compile_features(mjpeg-bench PRIVATE cxx_std_17)
target_include_directories(mjpeg-bench PRIVATE
  "${CMAKE_BINARY_DIR}" "${CMAKE_SOURCE_DIR}/src" "${CMAKE_CURRENT_SOURCE_DIR}")
target_compile_definitions(mjpeg-bench PRIVATE
  MJPEG_FRAME_SHA256="${MJPEG_FRAME_SHA256}")
target_link_libraries(mjpeg-bench PRIVATE
  benchmark::benchmark jpeg-static turbojpeg-static)
if(UNIX)
  target_link_libraries(mjpeg-bench PRIVATE m)
endif()
if(WITH_PROFILE)
  message(WARNING
    "WITH_PROFILE adds instrumentation overhead to mjpeg-bench timings.")
endif()
if(WITH_TESTS)
  add_test(NAME mjpeg-bench-smoke COMMAND mjpeg-bench
    --benchmark_min_time=0.001s --benchmark_min_warmup_time=0
    --benchmark_repetitions=1)
endif()
