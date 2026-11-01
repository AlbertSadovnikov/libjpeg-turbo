/* Compiler-decision probes, not timing microbenchmarks. All shifts require
 * 1 <= n <= 16 and n <= available <= 64 at their callers. */
#include <stdint.h>
#include <immintrin.h>

#define NOINLINE __attribute__((noinline,noclone))
#define OLD_EXTEND(x,n) ((x) + ((((x) - (1 << ((n)-1))) >> 31) & ((~0U << (n)) + 1)))

NOINLINE unsigned mask_signed(uint64_t bits,int available,int n)
{ return ((int)(bits >> (available-n))) & ((1 << n)-1); }
NOINLINE unsigned mask_unsigned(uint64_t bits,int available,int n)
{ return (unsigned)(bits >> (available-n)) & ((1U << n)-1U); }
NOINLINE unsigned mask_bounded(uint64_t bits,int available,int n)
{
  if(n<1 || n>16 || available<n || available>64) __builtin_unreachable();
  return ((int)(bits >> (available-n))) & ((1 << n)-1);
}
NOINLINE int receive_signed(uint64_t bits,int available,int n)
{
  int x=((int)(bits >> (available-n))) & ((1 << n)-1);
  return OLD_EXTEND(x,n);
}
NOINLINE int receive_unsigned(uint64_t bits,int available,int n)
{
  int x=(unsigned)(bits >> (available-n)) & ((1U << n)-1U);
  return OLD_EXTEND(x,n);
}
NOINLINE int receive_bounded(uint64_t bits,int available,int n)
{
  if(n<1 || n>16 || available<n || available>64) __builtin_unreachable();
  int x=((int)(bits >> (available-n))) & ((1 << n)-1);
  return OLD_EXTEND(x,n);
}
NOINLINE unsigned mask_needed_elsewhere(uint64_t bits,int available,int n,unsigned *mask)
{
  unsigned m=(1U<<n)-1;
  *mask=m;
  return (unsigned)(bits >> (available-n)) & m;
}
NOINLINE __attribute__((target("bmi2"))) unsigned force_bzhi(uint64_t bits,int available,int n)
{ return _bzhi_u32((unsigned)(bits >> (available-n)),n); }

/* Explicit opcode control for GCC/x86-64. BMI2 detection belongs at kernel
 * selection, not inside these per-operation wrappers. SHRX/SHLX preserve flags. */
static inline uint64_t force_shrx(uint64_t x,unsigned n)
{
  uint64_t out,count=n;
  __asm__("shrx {%2, %1, %0|%0, %1, %2}" : "=r"(out) : "r"(x),"r"(count));
  return out;
}
static inline uint64_t force_shlx(uint64_t x,unsigned n)
{
  uint64_t out,count=n;
  __asm__("shlx {%2, %1, %0|%0, %1, %2}" : "=r"(out) : "r"(x),"r"(count));
  return out;
}
NOINLINE __attribute__((target("bmi2"))) uint64_t explicit_shift_pair(uint64_t x,unsigned right,unsigned left)
{ return force_shlx(force_shrx(x,right),left); }

/* Small alias examples distinguish table reads from arithmetic eligibility.
 * short matches the signed 16-bit coefficient/table-field type on this target. */
NOINLINE short alias_reload(const short *table,short *out)
{ short first=table[0]; out[0]=first+1; return table[0]; }
NOINLINE short noalias_reload(const short *__restrict table,short *__restrict out)
{ short first=table[0]; out[0]=first+1; return table[0]; }

/* Aligned scalar values still use ordinary MOV on x86-64. */
NOINLINE uint64_t load_memcpy(const unsigned char *p)
{ uint64_t x; __builtin_memcpy(&x,p,8); return x; }
NOINLINE uint64_t load_memcpy_aligned(const unsigned char *p)
{ p=__builtin_assume_aligned(p,8); uint64_t x; __builtin_memcpy(&x,p,8); return x; }
