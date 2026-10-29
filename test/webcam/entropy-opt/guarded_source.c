/* Linux-only validation helper: each source chunk ends at a protected page.
 * It is not used in timed benchmarks. Outputs can be compared across builds.
 */
#define _DEFAULT_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include "jpeglib.h"

typedef struct {
  struct jpeg_source_mgr pub;
  const unsigned char *input;
  size_t size, position, chunk, capacity;
  unsigned char *mapping;
} guarded_source;

static void init_source(j_decompress_ptr c)
{
  guarded_source *s = (guarded_source *)c->src;
  s->position = 0;
  s->pub.bytes_in_buffer = 0;
}

static boolean fill_source(j_decompress_ptr c)
{
  guarded_source *s = (guarded_source *)c->src;
  size_t count = s->size - s->position;
  unsigned char *destination;
  if (count > s->chunk) count = s->chunk;
  if (count) {
    destination = s->mapping + s->capacity - count;
    memcpy(destination, s->input + s->position, count);
    s->position += count;
  } else {
    destination = s->mapping + s->capacity - 2;
    destination[0] = 0xff;
    destination[1] = JPEG_EOI;
    count = 2;
  }
  s->pub.next_input_byte = destination;
  s->pub.bytes_in_buffer = count;
  return TRUE;
}

static void skip_source(j_decompress_ptr c, long count)
{
  if (count <= 0) return;
  while ((size_t)count > c->src->bytes_in_buffer) {
    count -= (long)c->src->bytes_in_buffer;
    fill_source(c);
  }
  c->src->next_input_byte += count;
  c->src->bytes_in_buffer -= count;
}

static void term_source(j_decompress_ptr c) { (void)c; }

int main(int argc, char **argv)
{
  const size_t chunks[] = {1, 31, 2047, 2048, 2049, 4095, 4096, 4097, 8192, 65536};
  long page = sysconf(_SC_PAGESIZE);
  struct jpeg_decompress_struct c;
  struct jpeg_error_mgr error;
  if (argc < 2 || page <= 0) return 2;
  c.err = jpeg_std_error(&error);
  jpeg_create_decompress(&c);
  for (int f = 1; f < argc; f++) {
    FILE *file = fopen(argv[f], "rb");
    long size;
    unsigned char *input;
    if (!file || fseek(file, 0, SEEK_END)) return 3;
    size = ftell(file);
    if (size <= 0 || fseek(file, 0, SEEK_SET)) return 4;
    input = malloc((size_t)size);
    if (!input || fread(input, 1, size, file) != (size_t)size) return 5;
    fclose(file);
    for (size_t k = 0; k < sizeof(chunks)/sizeof(chunks[0]); k++) {
      guarded_source s;
      size_t bytes, stride;
      unsigned char *output;
      uint64_t hash = UINT64_C(14695981039346656037);
      memset(&s, 0, sizeof(s));
      s.input = input; s.size = (size_t)size; s.chunk = chunks[k];
      s.capacity = ((s.chunk + page - 1) / page) * page;
      s.mapping = mmap(NULL, s.capacity + page, PROT_READ | PROT_WRITE,
                       MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
      if (s.mapping == MAP_FAILED ||
          mprotect(s.mapping + s.capacity, page, PROT_NONE)) return 6;
      s.pub.init_source = init_source;
      s.pub.fill_input_buffer = fill_source;
      s.pub.skip_input_data = skip_source;
      s.pub.resync_to_restart = jpeg_resync_to_restart;
      s.pub.term_source = term_source;
      c.src = &s.pub;
      if (jpeg_read_header(&c, TRUE) != JPEG_HEADER_OK || c.data_precision != 8)
        return 7;
      c.out_color_space = JCS_EXT_BGR;
      if (!jpeg_start_decompress(&c)) return 8;
      stride = (size_t)c.output_width * c.output_components;
      bytes = stride * c.output_height;
      output = malloc(bytes);
      if (!output) return 9;
      while (c.output_scanline < c.output_height) {
        JSAMPROW row = output + c.output_scanline * stride;
        if (!jpeg_read_scanlines(&c, &row, 1)) return 10;
      }
      if (!jpeg_finish_decompress(&c) || error.num_warnings) return 11;
      for (size_t i = 0; i < bytes; i++) {
        hash ^= output[i]; hash *= UINT64_C(1099511628211);
      }
      printf("%d,%zu,%zu,%016llx\n",f-1,chunks[k],bytes,(unsigned long long)hash);
      free(output);
      munmap(s.mapping, s.capacity + page);
      c.src = NULL;
    }
    free(input);
  }
  jpeg_destroy_decompress(&c);
  return 0;
}
