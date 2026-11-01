/* Exhaustive valid amplitude values and synthetic fused-entry hit/miss checks.
 * Include the private source to exercise the exact inline kernels/layout. */
#include MJPEG_ASM_SOURCE
#include <stdint.h>

int main(void)
{
  unsigned long amplitudes = 0, pairs = 0;
  unsigned int n, x, prefix, k;
  multi_entry table[1024];
  for (n = 1; n <= 16; n++) {
    for (x = 0; x < (1U << n); x++) {
      int initial = n + ((x * 17U) % (65 - n));
      int left = initial;
      uint64_t low = initial == (int)n ? 0 :
        (UINT64_C(0xa5a5a5a5a5a5a5a5) >> (64 - (initial - n)));
      uint64_t word = ((uint64_t)x << (initial - n)) | low;
      int expected = x < (1U << (n - 1)) ? (int)x - (int)((1U << n) - 1) : (int)x;
      int actual = mjpeg_receive_asm(word, &left, n);
      if (actual != expected || left != initial - (int)n) {
        fprintf(stderr, "receive n=%u x=%u initial=%d got=%d expected=%d left=%d\n",
                n, x, initial, actual, expected, left);
        return 1;
      }
      amplitudes++;
    }
  }
  for (prefix = 0; prefix < 1024; prefix++) {
    multi_entry e = { (INT16)((int)prefix - 512), (INT16)(1000 - (int)prefix),
                      (UINT8)(prefix % 11), (UINT8)(1 + prefix % 16),
                      (UINT8)((prefix / 16) % 17), 2 };
    table[prefix] = e;
  }
  for (prefix = 0; prefix < 1024; prefix++) {
    for (k = 1; k < 64; k++) {
      JCOEF actual[80], expected[80];
      multi_entry e = table[prefix];
      int position = k, want_position = k, initial = 10 + prefix % 55;
      int left = initial, want_left = initial;
      int hit, want_hit = e.bits && k + e.step1 + e.step2 <= 64;
      uint64_t word = (uint64_t)prefix << (initial - 10);
      memset(actual, 0x5a, sizeof(actual));
      memcpy(expected, actual, sizeof(actual));
      if (want_hit) {
        want_left -= e.bits;
        want_position += e.step1 - 1;
        expected[jpeg_natural_order[want_position]] = e.value1;
        want_position += e.step2;
        expected[jpeg_natural_order[want_position]] = e.value2;
      }
      hit = mjpeg_pair_asm(word, &left, &position, actual, table);
      if (hit != want_hit || left != want_left || position != want_position ||
          memcmp(actual, expected, sizeof(actual))) {
        fprintf(stderr, "pair prefix=%u k=%u hit=%d expected=%d\n", prefix, k, hit, want_hit);
        return 1;
      }
      pairs++;
    }
  }
  printf("Checked %lu amplitudes and %lu fused-entry hit/miss cases.\n", amplitudes, pairs);
  return 0;
}
