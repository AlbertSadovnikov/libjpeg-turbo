#ifndef MJPEG_BENCHMARK_HUFFMAN_TABLES_H
#define MJPEG_BENCHMARK_HUFFMAN_TABLES_H

#ifdef __cplusplus
extern "C" {
#endif

struct mjpeg_bench_huffman_tables;
struct mjpeg_bench_huffman_tables *
mjpeg_bench_create_huffman_tables(j_decompress_ptr cinfo);
void mjpeg_bench_rebuild_huffman_tables(
  j_decompress_ptr cinfo, struct mjpeg_bench_huffman_tables *tables);

#ifdef __cplusplus
}
#endif
#endif
