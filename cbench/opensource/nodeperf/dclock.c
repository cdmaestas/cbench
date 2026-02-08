/*
 * Timing routines
 *
 * includes CPU clocks, CPU frequency and CPU time in seconds measurement
 *
 * Architectures: IA32 ('rdtsc' instruction supporting), IA64
 * Operational systems: Windows, Linux
 *
 */

/*
 * Details:
 * You should define macronames to get an appropriate code
 * "_IA64_" for IA64, "_LINUX" for Linux, Win32 output code is default
 *
 */

/*-------------------------------------------------
 *  header files
 *------------------------------------------------*/

#ifdef _LINUX

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#else /* Windows */

#include <windows.h>

#endif

#include <time.h>

/*-------------------------------------------------
 * interface names
 *------------------------------------------------*/

#ifdef _LINUX

#ifndef TCLOCK
#define TCLOCK          tclock_
#endif
#ifndef SECOND
#define SECOND          second_
#endif
#ifndef DSECND
#define DSECND          dsecnd_
#endif
#ifndef GETCPUFREQUENCY
#define GETCPUFREQUENCY getcpufrequency_
#endif

#endif

/*-------------------------------------------------
 * Here are these routines implemented
 *------------------------------------------------*/

double TCLOCK();
float  SECOND();
double DSECND();
double GETCPUFREQUENCY();

#ifdef _LINUX

double GETCPUFREQUENCY_CPUINFO();
double GETCPUFREQUENCY_CLOCK ();

#else /* Windows */

double GETCPUFREQUENCY_WINAPI();
double GETCPUFREQUENCY_CLOCK ();

#endif


#ifdef _LINUX
#ifndef _IA64_
static unsigned usec, sec;
static unsigned start=0, startu;
static long long foo;

static inline void atlas_microtime(unsigned *lo, unsigned *hi)
{
  __asm __volatile (
        ".byte 0x0f; .byte 0x31   # RDTSC instruction\n\t"
        "movl    %%edx,%0          # High order 32 bits\n\t"
        "movl    %%eax,%1          # Low order 32 bits\n\t"
                : "=g" (*hi), "=g" (*lo) :: "eax", "edx");
}
#endif
#endif

/*-------------------------------------------------
 * double TCLOCK( void )
 *
 * gets CPU clocks.
 * Invokes assembler instructions
 *------------------------------------------------*/

double TCLOCK( void ) {

#ifdef _LINUX

#ifdef _IA64_
/*  asm statements are not supported in Electron IA64 Linux */
#ifndef _GCC_
   __int64 RDTSC();

   return (double) RDTSC();

/* RDTSC is equivalent to
        mov r8=ar.itc
        br.ret.sptk.few  b0
*/
#else
/* asm statements are supported in GCC IA64 Linux */
    unsigned long result;

    __asm__ __volatile__( "mov %0=ar.itc" : "=r"(result) :: "memory");
    return ( (double) result);
#endif

#else /* IA32 Linux */

/*
   asm (
      "rdtsc ;
      movl %eax, -8(%esp) ;
      movl %edx, -4(%esp) ;
      fildq -8(%esp)"
   );
*/
  atlas_microtime(&usec, &sec);

  foo = sec;
  foo = (foo << 32) + usec;
  return((double)foo);

#endif

#else /* Windows */

#ifdef _IA64_

   unsigned __int64 __getReg(int whichReg);
   #pragma intrinsic(__getReg);
   #define INL_REGID_APITC 3116

   return (double) __getReg(INL_REGID_APITC);

#else /* IA32 */

   _asm {
      rdtsc
      mov DWORD PTR [esp-8], eax
      mov DWORD PTR [esp-4], edx
      fild QWORD PTR [esp-8]
   }

#endif

#endif

}

/*-------------------------------------------------
 * double DSECND()
 *
 * gets CPU time in seconds
 *------------------------------------------------*/

double DSECND() {
   static int first = 1;
   static double freq;

   if( first ) {
      freq = GETCPUFREQUENCY();
      first = 0;
   }
   return TCLOCK() / freq;
}

/*-------------------------------------------------
 * float SECOND()
 *
 * gets CPU time in seconds
 *------------------------------------------------*/

float SECOND() {return (float) DSECND();}


/*-------------------------------------------------
 * double GETCPUFREQUENCY()
 *
 * gets CPU freqeuency in Hz
 * First try to get a more reliable number
 *------------------------------------------------*/

#define BAD_FREQUENCY -1.0

double GETCPUFREQUENCY()
{
   double freqclk = GETCPUFREQUENCY_CLOCK();
   double freq =
#ifdef _LINUX
         GETCPUFREQUENCY_CPUINFO();
#else /* Windows */
         GETCPUFREQUENCY_WINAPI();
#endif

   if ( freq == BAD_FREQUENCY ) freq = freqclk;
#ifndef _LINUX
   else if ( (freq>=freqclk) && ((freq-freqclk)/freq) > 0.1 ) freq = freqclk;
   else if ( (freq <freqclk) && ((freqclk-freq)/freq) > 0.1 ) freq = freqclk;
#endif

   return freq;
}

#ifdef _LINUX

/*-------------------------------------------------
 * double GETCPUFREQUENCY_CPUINFO()
 *
 * gets CPU freqeuency in Hz (Linux only)
 * from /proc/cpuinfo
 *------------------------------------------------*/

double GETCPUFREQUENCY_CPUINFO() {
   #define BUFLEN 110

   FILE* sysinfo;
   char* ptr;
   char buf[BUFLEN];
   char key[] = "cpu MHz";
   int keylen = sizeof( key ) - 1;
   double freq = BAD_FREQUENCY;

   sysinfo = fopen( "/proc/cpuinfo", "r" );
   if( sysinfo != NULL ) {
      while( fgets( buf, BUFLEN, sysinfo ) != NULL ) {
         if( !strncmp( buf, key, keylen ) ) {
            ptr = strstr( buf, ":" );
            freq = atof( ptr+1 ) * 1000000.0;
            break;
         }
      }
      fclose( sysinfo );
   }

   return freq;
}

#else /* Windows */

/*-------------------------------------------------
 * double GETCPUFREQUENCY_WINAPI()
 *
 * gets CPU freqeuency in Hz (Windows only)
 * from High Resolution Performance Counter
 *------------------------------------------------*/

double GETCPUFREQUENCY_WINAPI()
{
   #define SLEEP_TIME 200  /* in mSec */

   double time, clock1, clock2, tick1, tick2;
   LARGE_INTEGER pc1, pc2, pf;

   if( QueryPerformanceFrequency( &pf ) && QueryPerformanceCounter( &pc1 ) ) {
      QueryPerformanceCounter( &pc1 );
      clock1 = TCLOCK();                // current CPU clocks

      Sleep( SLEEP_TIME );     // wait some time

      QueryPerformanceCounter( &pc2 );
      clock2 = TCLOCK();                // current CPU clocks

      tick1 = (double)pc1.u.HighPart * 65536.0 * 65536.0 + (double)pc1.u.LowPart;
      tick2 = (double)pc2.u.HighPart * 65536.0 * 65536.0 + (double)pc2.u.LowPart;
      time = (tick2 - tick1) / ((double)pf.u.HighPart * 65536.0 * 65536.0 + (double)pf.u.LowPart);
      return (clock2 - clock1) / time; // it's CPU frequency
   } else {
      return BAD_FREQUENCY;
   }
}

#endif

/*-------------------------------------------------
 * double GETCPUFREQUENCY_CLOCK()
 *
 * gets CPU freqeuency in Hz
 * with standard clock() routine
 *------------------------------------------------*/
/*
#ifdef _LINUX
   #define CLOCKS_PER_SEC 1000000
#endif
*/
double GETCPUFREQUENCY_CLOCK() {
   #define TIME_LIMIT 1.0  /* in Sec */

   double time, clock1, clock2, tick1, tick2;

   tick1 = (double) clock();  // current time in msec
   clock1 = TCLOCK();         // current CPU clocks

   while( ((double) clock() - tick1) < (CLOCKS_PER_SEC * TIME_LIMIT) );   // wait some time
//   Sleep( TIME_LIMIT );       // wait some time

   tick2 = (double) clock();  // current time in msec
   clock2 = TCLOCK();                // current CPU clocks
   time = (tick2 - tick1) / CLOCKS_PER_SEC;

   return (clock2 - clock1) / time; // it's CPU frequency
}


