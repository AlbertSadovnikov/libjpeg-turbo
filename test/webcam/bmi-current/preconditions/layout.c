/* Include the private experiment solely to inspect its real types/layout. */
#include MJPEG_AUDIT_SOURCE
#include <stddef.h>
#include <stdio.h>

int main(int argc,char **argv)
{
  if(argc!=2) return 2;
  FILE *input=fopen(argv[1],"rb"); if(!input) return 2;
  struct jpeg_decompress_struct c;
  struct jpeg_error_mgr e;
  c.err=jpeg_std_error(&e); jpeg_create_decompress(&c); jpeg_stdio_src(&c,input);
  jpeg_read_header(&c,TRUE); jpeg_start_decompress(&c);
  printf("{\"entry_size\":%zu,\"entry_alignment\":%zu,\"lookup_offset\":%zu,\"tables\":[",
         sizeof(multi_entry),_Alignof(multi_entry),offsetof(fused_ac_cache,lookup));
  int first=1;
  for(int i=0;i<NUM_HUFF_TBLS;i++) {
    fused_ac_cache *cache=(fused_ac_cache *)c.master->fused_ac_cache[i];
    if(!cache) continue;
    size_t address=(size_t)cache->lookup;
    unsigned int crossing=0;
    for(unsigned int j=0;j<(1U<<MJPEG_FUSED_BITS);j++)
      crossing+=((address+j*sizeof(multi_entry))&63)+sizeof(multi_entry)>64;
    printf("%s{\"table\":%d,\"base_mod8\":%zu,\"base_mod64\":%zu,\"entries_crossing_cacheline\":%u}",
           first?"":",",i,address&7,address&63,crossing);
    first=0;
  }
  puts("]}"); jpeg_abort_decompress(&c); jpeg_destroy_decompress(&c); fclose(input);
  return 0;
}
