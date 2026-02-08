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


void getientropy(unsigned int *entropy)
{
	int urandom_fd;
	
	urandom_fd=open("/dev/urandom",O_RDONLY);
	read(urandom_fd,entropy,4);
	return;
}



int main (int argc, char **argv)
{
	unsigned int entropy[1];
	getientropy(entropy);
	printf("%u\n",*(entropy));
	return 0;
}


