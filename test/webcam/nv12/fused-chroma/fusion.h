#ifndef MJPEG_EXPERIMENT_FUSION_H
#define MJPEG_EXPERIMENT_FUSION_H
#ifdef __cplusplus
extern "C" {
#endif
/* Benchmark-only registration. mode: 0 normal, 1 exact accurate, 2 reduced. */
int mjpeg_fusion_begin(j_decompress_ptr, unsigned char *, int, int);
void mjpeg_fusion_end(void);
int mjpeg_fusion_mcu(j_decompress_ptr, JBLOCKROW *, JSAMPIMAGE, JDIMENSION);
void mjpeg_chroma_reduced_test(const JCOEF *,const JCOEF *,unsigned char *,int);
#ifdef __cplusplus
}
#endif
#endif
