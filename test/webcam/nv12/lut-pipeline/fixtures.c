/* Same-size 4:2:2 JPEG inputs for NV12-path lookup/refill boundary checks. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "jpeglib.h"
int main(int argc,char **argv){
  if(argc!=4)return 2;
  FILE *input=fopen(argv[1],"rb"),*output=fopen(argv[2],"wb");if(!input||!output)return 3;
  struct jpeg_decompress_struct d;struct jpeg_compress_struct c;struct jpeg_error_mgr de,ce;
  d.err=jpeg_std_error(&de);c.err=jpeg_std_error(&ce);jpeg_create_decompress(&d);jpeg_create_compress(&c);
  jpeg_stdio_src(&d,input);jpeg_read_header(&d,TRUE);jvirt_barray_ptr *arrays=jpeg_read_coefficients(&d);
  if(!strcmp(argv[3],"dense")||!strcmp(argv[3],"tail63")||!strcmp(argv[3],"zeroac")){
    for(int ci=0;ci<d.num_components;ci++)for(JDIMENSION y=0;y<d.comp_info[ci].height_in_blocks;y++){
      JBLOCKARRAY row=d.mem->access_virt_barray((j_common_ptr)&d,arrays[ci],y,1,TRUE);
      for(JDIMENSION x=0;x<d.comp_info[ci].width_in_blocks;x++){
        if(!strcmp(argv[3],"dense"))for(int k=1;k<64;k++)row[0][x][k]=(k%2)?1:-1;
        else if(!strcmp(argv[3],"zeroac"))memset(row[0][x]+1,0,63*sizeof(JCOEF));
        else row[0][x][63]=1;
      }
    }
  }
  jpeg_stdio_dest(&c,output);jpeg_copy_critical_parameters(&d,&c);
  if(!strcmp(argv[3],"rst1"))c.restart_interval=1;
  if(!strcmp(argv[3],"optimized"))c.optimize_coding=TRUE;
  if(!strcmp(argv[3],"progressive"))jpeg_simple_progression(&c);
  jpeg_write_coefficients(&c,arrays);jpeg_finish_compress(&c);jpeg_finish_decompress(&d);
  jpeg_destroy_compress(&c);jpeg_destroy_decompress(&d);fclose(input);fclose(output);return 0;
}
