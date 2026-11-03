/* Coefficient-domain JPEG fixtures; no RGB conversion or image utilities. */
#include <stdio.h>
#include <stdlib.h>
#include "jpeglib.h"
int main(int argc,char **argv) {
 if(argc!=6)return 2;
 const int w=atoi(argv[2]),h=atoi(argv[3]),restart=atoi(argv[4]),progressive=atoi(argv[5]);
 FILE *out=fopen(argv[1],"wb");if(!out)return 3;
 struct jpeg_compress_struct c;struct jpeg_error_mgr e;
 c.err=jpeg_std_error(&e);jpeg_create_compress(&c);jpeg_stdio_dest(&c,out);
 c.image_width=w;c.image_height=h;c.input_components=3;c.in_color_space=JCS_YCbCr;
 jpeg_set_defaults(&c);c.comp_info[0].h_samp_factor=2;c.comp_info[0].v_samp_factor=1;
 c.comp_info[1].h_samp_factor=c.comp_info[2].h_samp_factor=1;
 c.comp_info[1].v_samp_factor=c.comp_info[2].v_samp_factor=1;
 unsigned int q[64];for(int i=0;i<64;i++)q[i]=2+i%19;
 jpeg_add_quant_table(&c,2,q,100,TRUE);c.comp_info[2].quant_tbl_no=2;
 c.restart_interval=restart;if(progressive)jpeg_simple_progression(&c);
 jvirt_barray_ptr a[3];int widths[3]={(w+15)/16*2,(w+15)/16,(w+15)/16},height=(h+7)/8;
 for(int k=0;k<3;k++)a[k]=(*c.mem->request_virt_barray)((j_common_ptr)&c,JPOOL_IMAGE,TRUE,widths[k],height,1);
 jpeg_write_coefficients(&c,a);
 for(int k=0;k<3;k++)for(int y=0;y<height;y++) {
  JBLOCKARRAY row=(*c.mem->access_virt_barray)((j_common_ptr)&c,a[k],y,1,TRUE);
  for(int x=0;x<widths[k];x++)for(int j=0;j<64;j++)
   row[0][x][j]=j==0?(x*31+y*17+k*43)%501-250:((x*13+y*7+k*3+j)%5==0?(j%7)-3:0);
 }
 jpeg_finish_compress(&c);jpeg_destroy_compress(&c);fclose(out);return 0;
}
