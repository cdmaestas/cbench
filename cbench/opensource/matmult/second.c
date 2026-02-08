/*
 * C wrapper to help with Fortran LAPACK linkage in some 
 * situtaions
 */


#define DSECND          dsecnd_

/*-------------------------------------------------
 * float SECOND()
 *
 * gets CPU time in seconds
 *------------------------------------------------*/

double second() {return DSECND();}
