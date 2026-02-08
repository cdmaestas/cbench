/*
 *
 * rewrite.c -- this is an filesystem torture test.  Run lots of
 *  copies of this in parallel in a single directory, either locally or
 * via NFS.
 *
 * Written by Theodore Ts'o, tytso@valinux.com
 */

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <sys/types.h>
#include <sys/file.h>

main(int argc, char **argv)
{
        int     fd, i;
        char    fn[128];
        char    buf[4096];

        sprintf(fn, "./ttest%d", getpid());
        fd = open(fn, O_CREAT|O_RDWR|O_TRUNC, 0600);
        if (fd < 0) {
                perror("open");
                exit(1);
        }
        memset(buf, 0xe5, sizeof(buf));
        while (1) {
                if (lseek(fd, (12+256+256*256) * 1024, SEEK_SET)
                    == (off_t) -1) {
                        perror("lseek");
                }
                for (i=0; i < 32; i++) {
                        if (write(fd, buf, sizeof(buf)) != sizeof(buf)) {
                                if (errno != ENOSPC)  
                                        perror("write");
                                break;
                        }
                }
                ftruncate(fd, 0);
        }
}


