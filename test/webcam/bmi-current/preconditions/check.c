/* Semantic checks for the executable compiler probes and explicit wrappers. */
#include "probes.c"
#include <stdio.h>

int main(void)
{
  if(!__builtin_cpu_supports("bmi2")) return 77;
  unsigned long long checked=0;
  for(int n=1;n<=16;n++) {
    for(unsigned x=0;x<(1U<<n);x++) {
      uint64_t bits=(uint64_t)x<<16;
      int expected=x<(1U<<(n-1))?(int)x-(int)((1U<<n)-1):(int)x;
      if(mask_signed(bits,n+16,n)!=x || mask_unsigned(bits,n+16,n)!=x ||
         mask_bounded(bits,n+16,n)!=x || force_bzhi(bits,n+16,n)!=x ||
         receive_signed(bits,n+16,n)!=expected || receive_unsigned(bits,n+16,n)!=expected ||
         receive_bounded(bits,n+16,n)!=expected) return 1;
      checked++;
    }
  }
  uint64_t bits=0x9abc1234def05678ULL;
  for(unsigned right=0;right<64;right++)
    for(unsigned left=0;left<64;left++)
      if(explicit_shift_pair(bits,right,left)!=((bits>>right)<<left)) return 1;
  short same=7,other=0;
  if(alias_reload(&same,&same)!=8 || noalias_reload(&same,&other)!=8 || other!=9) return 1;
  unsigned char bytes[16]={0};
  for(int offset=0;offset<8;offset++) (void)load_memcpy(bytes+offset);
  printf("Checked %llu amplitude cases and 4096 explicit shift pairs.\n",checked);
  return 0;
}
