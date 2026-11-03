#include <stdio.h>
#include <stdlib.h>
#include "jpeglib.h"
int main(int argc,char **argv){if(argc!=5)return 2;FILE *in=fopen(argv[1],"rb"),*out=fopen(argv[2],"wb");if(!in||!out)return 3;struct jpeg_decompress_struct d;struct jpeg_compress_struct c;struct jpeg_error_mgr de,ce;d.err=jpeg_std_error(&de);c.err=jpeg_std_error(&ce);jpeg_create_decompress(&d);jpeg_create_compress(&c);jpeg_stdio_src(&d,in);jpeg_read_header(&d,TRUE);jvirt_barray_ptr *a=jpeg_read_coefficients(&d);jpeg_stdio_dest(&c,out);jpeg_copy_critical_parameters(&d,&c);c.restart_interval=strtoul(argv[3],NULL,10);c.optimize_coding=atoi(argv[4]);jpeg_write_coefficients(&c,a);jpeg_finish_compress(&c);jpeg_finish_decompress(&d);jpeg_destroy_compress(&c);jpeg_destroy_decompress(&d);fclose(in);fclose(out);return 0;}
