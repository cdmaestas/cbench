/*
 * prandom.c
 *
 * This is a program to generate large amounts of pseudorandom
 * data quickly, using /dev/urandom and some fast bitwise
 * operations to turn a little bit of random data into a whole
 * lot of somewhat less random data :)
 *
 * Needless to say, don't use this for encryption or anything
 * like that.
 *
 * Copyright (C) 1999 VA Linux Systems, All Rights Reserved.
 *
 * You may redistribute this program under the terms of the General
 * Public License, version 2, or any later version at your option.
 *
 * Program author:  Jason T. Collins <jcollins@valinux.com>
 *
 */



#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>


void getentropy(char *entropy)
{
	int urandom_fd;
	
	urandom_fd=open("/dev/urandom",O_RDONLY);
	read(urandom_fd,entropy,1024);
	return;
}



/* Generate pseudorandom data to stdout. Long parameter is kilobytes */
int prandom (long quantity)
{
	char entropy[1024];
	char pdata[1024];
	int x,y;
	int xlim = 1024;
	long kb_rem = quantity;

	while(kb_rem > 0) {
		getentropy(entropy);
		if (kb_rem < 1024) {
			xlim = kb_rem;
		}
		for(x=0;x<xlim;x++) {
			for(y=0;y<1024;y++) {
				pdata[y] = entropy[x] ^ entropy[y];
			}
		write(1, pdata, 1024);
		}
		kb_rem = kb_rem - 1024;
	}
	
	return 0;
}



int main (int argc, char **argv)
{
	if (argc < 2) {
		printf("Usage: %s [kb]\n",argv[0]);
		printf("       kb is an int for KB of data output\n");
		return 2;
	} else {
		return prandom(atol(argv[1]));
	}
}


