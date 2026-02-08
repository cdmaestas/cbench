/* chartst.c (C) 1999 VA Linux Systems, all rights reserved */
/* Author:  jcollins@valinux.com */
/* You may redistribute this program under the terms of the GNU General
   Public License, version 2, or a later version at your option. */

/* simple little proggie to generate characters */

#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <signal.h>

void handler(int i) {
	exit (0);
}

int main(int argc, char **argv)
{
	char *outstring;
	int timeout;
	if(argc < 2) {
		timeout = 0;
	} else {
		timeout = strtol(argv[1],NULL,0);
	}
	if(argc < 3) {
		outstring=(char *) malloc(2);
		outstring[0]='X';
		outstring[1]=(char) 0;
	} else {
		outstring=(char *) malloc(strlen(argv[2]));
		strcpy(outstring,argv[2]);
	}
	signal(SIGALRM,&handler);
	alarm(timeout);
	while (1) {
	   	fputs(outstring, stdout);
        }
}
