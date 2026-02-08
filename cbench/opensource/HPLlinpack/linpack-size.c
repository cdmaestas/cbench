#include<stdio.h>
#include<math.h>
#include<stdlib.h>

#define MB (1024UL*1024UL)

int main( int ac, char **av )
{
    long imemsize;
    long nodes;
    long result;
    double factor1 = 0.90;
    double factor2 = 0.80;
    double factor3 = 0.70;
    double factor4 = 0.60;

    if ( ac < 3 ) {
        fprintf(stderr,"usage: %s <memory in MB> <number of nodes>\n", av[0]);
        exit(1);
    }

    imemsize = atol( av[1] );
    nodes    = atol( av[2] );
    result   = (long)( sqrt( (double)imemsize * MB / 8 * nodes ) );

    printf("%3.0f%% matrix size = %ld\n", 100.0,       result);
    printf("%3.0f%% matrix size = %ld\n", factor1*100, (long)(result*factor1));
    printf("%3.0f%% matrix size = %ld\n", factor2*100, (long)(result*factor2));
    printf("%3.0f%% matrix size = %ld\n", factor3*100, (long)(result*factor3));
    printf("%3.0f%% matrix size = %ld\n", factor4*100, (long)(result*factor4));

    return 0;
}
