/*****************************************************************************

 name:		meminfo()

 purpose:	Parse the /proc/meminfo file for memory usage

 author: 	d.w. doerfler, 9223

###############################################################################
#    Copyright (2005) Sandia Corporation.  Under the terms of Contract
#    DE-AC04-94AL85000 with Sandia Corporation, the U.S. Government retains
#    certain rights in this software
#
#    This file is part of Cbench.
#
#    Cbench is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    any later version.
#
#    Cbench is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Cbench; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
###############################################################################

*****************************************************************************/

#include <stdio.h>
#include <string.h>
#include "meminfo.h"

int meminfo_(MEMINFO *meminfo)
{
  FILE *fp;
  char buf[MAXLINE_SIZE], qualifier[MAXLINE_SIZE];
  meminfo_t value;

  if ((fp = fopen("/proc/meminfo", "r")) == NULL)
    return (1);

  memset(meminfo, 0, sizeof(MEMINFO));
  while (fgets(buf, MAXLINE_SIZE, fp) != NULL)
  {
    if (sscanf(buf, "%s %lu", qualifier, &value))
    {
      if (!strncmp("MemTotal:", qualifier, sizeof("MemTotal:")))
        meminfo->total = value << 10;
      else if (!strncmp("MemFree:", qualifier, sizeof("MemFree:")))
        meminfo->free = value << 10;
      else if (!strncmp("MemShared:", qualifier, sizeof("MemShared:")))
        meminfo->shared = value << 10;
      else if (!strncmp("Buffers:", qualifier, sizeof("Buffers:")))
        meminfo->buffers = value << 10;
      else if (!strncmp("Cached:", qualifier, sizeof("Cached:")))
        meminfo->cached = value << 10;
      else if (!strncmp("SwapTotal:", qualifier, sizeof("SwapTotal:")))
        meminfo->swap_total = value << 10;
      else if (!strncmp("SwapFree:", qualifier, sizeof("SwapFree:")))
        meminfo->swap_free = value << 10;
    }
  }

  fclose (fp);
  return(0);
}

int meminfo(MEMINFO *meminfo)
{
  return (meminfo_(meminfo));
}
