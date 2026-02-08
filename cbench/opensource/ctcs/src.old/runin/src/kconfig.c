/* kconfig.c (C) 1999 VA Linux Systems, all rights reserved */
/* Author:  jcollins@valinux.com */
/* You may redistribute this program under the terms of the GNU General
   Public License, version 2, or a later version at your option. */

/* simple little proggie to generate return characters */

#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <signal.h>

int main(int argc, char **argv)
{
	char *outstring;
	outstring=(char *) malloc(2);
	outstring[0]='\n';
	outstring[1]=(char) 0;
	while (1) {
	   	fputs(outstring, stdout);
        }
}
