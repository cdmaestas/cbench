#ifndef MEMORY_H
#define MEMORY_H

struct memory {
	unsigned long total_mem;
	unsigned long used_mem;
	unsigned long free_mem;
	unsigned long shared_mem;
	unsigned long buffer_mem;
	unsigned long cached_mem;
	
	unsigned long total_swap;
	unsigned long used_swap;
	unsigned long free_swap;
};

void meminfo( struct memory * );

#endif
