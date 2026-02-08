#include <stdio.h>
#include "memory.h"

#define LINESIZE 1024

void meminfo( struct memory *m ) {
  FILE *f;
  char line1[LINESIZE], qualifier[LINESIZE];
  unsigned long value;

  f = fopen("/proc/meminfo", "r");

  while (fgets(line1, LINESIZE-1, f) != NULL)
  {
    if (sscanf(line1, "%s %lu", qualifier, &value))
    {
      if (!strncmp("MemTotal:", qualifier, sizeof("MemTotal:")))
        m->total_mem = value << 10;
      else if (!strncmp("MemFree:", qualifier, sizeof("MemFree:")))
        m->free_mem = value << 10;
      else if (!strncmp("MemShared:", qualifier, sizeof("MemShared:")))
        m->shared_mem = value << 10;
      else if (!strncmp("Buffers:", qualifier, sizeof("Buffers:")))
        m->buffer_mem = value << 10;
      else if (!strncmp("Cached:", qualifier, sizeof("Cached:")))
        m->cached_mem = value << 10;
      else if (!strncmp("SwapTotal:", qualifier, sizeof("SwapTotal:")))
        m->total_swap = value << 10;
      else if (!strncmp("SwapFree:", qualifier, sizeof("SwapFree:")))
        m->free_swap = value << 10;
    }
  }

  fclose(f);
/* 
	 &(m->used_mem), 
	 &(m->used_swap), 
*/
}
