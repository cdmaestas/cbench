/* meminfo.h

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
*/

/* 64-bit quantity */
typedef unsigned long meminfo_t;

typedef struct {
    meminfo_t total;
    meminfo_t free;
    meminfo_t shared;
    meminfo_t buffers;
    meminfo_t cached;
    meminfo_t swap_total;
    meminfo_t swap_free;
} MEMINFO;

#define MAXLINE_SIZE 80

int meminfo(MEMINFO *);
