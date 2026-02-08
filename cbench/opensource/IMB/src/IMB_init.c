/*****************************************************************************
 *                                                                           *
 * Copyright (c) 2003-2007 Intel Corporation.                                *
 * All rights reserved.                                                      *
 *                                                                           *
 *****************************************************************************

This code is covered by the Community Source License (CPL), version
1.0 as published by IBM and reproduced in the file "license.txt" in the
"license" subdirectory. Redistribution in source and binary form, with
or without modification, is permitted ONLY within the regulations
contained in above mentioned license.

Use of the name and trademark "Intel(R) MPI Benchmarks" is allowed ONLY
within the regulations of the "License for Use of "Intel(R) MPI
Benchmarks" Name and Trademark" as reproduced in the file
"use-of-trademark-license.txt" in the "license" subdirectory. 

THE PROGRAM IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, EITHER EXPRESS OR IMPLIED INCLUDING, WITHOUT
LIMITATION, ANY WARRANTIES OR CONDITIONS OF TITLE, NON-INFRINGEMENT,
MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE. Each Recipient is
solely responsible for determining the appropriateness of using and
distributing the Program and assumes all risks associated with its
exercise of rights under this Agreement, including but not limited to
the risks and costs of program errors, compliance with applicable
laws, damage to or loss of data, programs or equipment, and
unavailability or interruption of operations.

EXCEPT AS EXPRESSLY SET FORTH IN THIS AGREEMENT, NEITHER RECIPIENT NOR
ANY CONTRIBUTORS SHALL HAVE ANY LIABILITY FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING
WITHOUT LIMITATION LOST PROFITS), HOWEVER CAUSED AND ON ANY THEORY OF
LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OR
DISTRIBUTION OF THE PROGRAM OR THE EXERCISE OF ANY RIGHTS GRANTED
HEREUNDER, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGES. 

EXPORT LAWS: THIS LICENSE ADDS NO RESTRICTIONS TO THE EXPORT LAWS OF
YOUR JURISDICTION. It is licensee's responsibility to comply with any
export regulations applicable in licensee's jurisdiction. Under
CURRENT U.S. export regulations this software is eligible for export
from the U.S. and can be downloaded by or otherwise exported or
reexported worldwide EXCEPT to U.S.  embargoed destinations which
include Cuba, Iraq, Libya, North Korea, Iran, Syria, Sudan,
Afghanistan and any other country to which the U.S. has embargoed
goods and services.

 ***************************************************************************

For more documentation than found here, see

[1] doc/ReadMe_IMB.txt 

[2] Intel (R) MPI Benchmarks
    Users Guide and Methodology Description
    In 
    doc/IMB_ug.pdf
    
 File: IMB_init.c 

 Modifications IMB_2.3 => IMB_3.0:
 Better argument checking and error messages
 Include -h flag for help
 2 new auxiliary functions:
 IMB_chk_arg_int
 IMB_chk_arg_file

 Implemented functions: 

 IMB_basic_input;
 IMB_chk_arg_int
 IMB_chk_arg_file
 IMB_get_rank_portion;
 IMB_init_communicator;
 IMB_set_communicator;
 IMB_valid;
 IMB_set_default;

 ***************************************************************************/





#include "IMB_declare.h"
#include "IMB_benchmark.h"

/* IMB 3.1 << */
#include "IMB_mem_info.h"
/* >> IMB 3.1  */

#include "IMB_prototypes.h"

/********************************************************************/


int IMB_chk_arg_int(int* val, char ***argv, int *argc, int iarg)
{
/* Checks command line argument for being nonnegative integer */
int ok;
ok=1;
if( iarg < *argc ){
int tst=IMB_str_atoi((*argv)[iarg]);
if( tst>=0 ) {
*val=tst;
}
else ok=0;
}
else ok=0;

return ok;
}


int IMB_chk_arg_file(FILE** fd, char ***argv, int *argc, int iarg)
{
/* Checks command line argument for being a file */
int ok;
*fd=(FILE*)NULL;
ok=1;
if( iarg < *argc ){
FILE* tst=(FILE*) fopen((*argv)[iarg],"r");
if( tst ) {
*fd=tst;
}
else ok=0;
}
else ok=0;

return ok;
}

#define N_baseinfo 13
/* IMB 3.1 << */
#define N_base_f_info 3  /* for float data */
/* >> IMB 3.1  */

/* IMB 3.1 << */
/*
   new "ITERATIONS" object for repetition count scheduling 
 
   major changes in interpreting the command line
*/

int IMB_basic_input(struct comm_info* c_info, struct Bench** P_BList, 
                    struct iter_schedule* ITERATIONS,
                    int *argc, char ***argv, int* NP_min)
/* >> IMB 3.1  */
/*



Input variables: 

-argc                 (type int *)                      
                      Number of command line arguments
                      

-argv                 (type char ***)                      
                      List of command line arguments
                      


Output variables: 

-NP_min               (type int*)                      
                      Minimum number of processes to run (-npmin command line argument)
                      

-P_BList              (type struct Bench**)                      
                      (For explanation of struct Bench type:
                      describes all aspects of modes of a benchmark;
                      see [1] for more information)
                      
                      Address of list of benchmarks to run;
                      list is set up.
                      

-c_info               (type struct comm_info*)                      
                      Collection of all base data for MPI;
                      see [1] for more information
                      


*/
{
  int i,n_cases,n_lens,iarg,iarg_msg;
  int deflt;
  int * ALL_INFO;
  char** DEFC, **CMT;
/* IMB 3.1 << */
  float ALL_F_INFO[N_base_f_info];
/* >> IMB 3.1  */

  int ok;
/* IMB_3.0 */
  int help_only;
  help_only=0;

  *P_BList = (struct Bench *)NULL;
/* IMB 3.1 << */
  ITERATIONS->n_sample=0;
  ITERATIONS->off_cache=0;
  ITERATIONS->cache_size=-1;
  ITERATIONS->s_offs = ITERATIONS->r_offs = 0;
  ITERATIONS->s_cache_iter = ITERATIONS->r_cache_iter = 1;
  ITERATIONS->msgspersample=MSGSPERSAMPLE;
  ITERATIONS->msgs_nonaggr=MSGS_NONAGGR;
  ITERATIONS->overall_vol=OVERALL_VOL;
  ITERATIONS->iter_dyn=0;
  ITERATIONS->numiters=(int*)NULL;
/* >> IMB 3.1  */

  MPI_Comm_rank(MPI_COMM_WORLD,&c_info->w_rank);
  MPI_Comm_size(MPI_COMM_WORLD,&c_info->w_num_procs);
  
  unit = stdout; 
  if( c_info->w_rank == 0 && strlen(OUTPUT_FILENAME) > 0 )
    unit = fopen(OUTPUT_FILENAME,"w"); 

  deflt = 0;
  ok = 0;
  iarg_msg=-1;

  c_info->group_mode = -1;
#ifdef MPIIO
  *NP_min=1;
#else
  *NP_min=2;
#endif

  if( c_info->w_rank == 0 )
  {
/* Interpret command line */
  n_lens = 0;

  if( *argc <= 1 )
    {
      /* Take default */
      deflt = 1;
    }
  else
    { 
      n_cases = *argc-1;

      iarg = 1;
       
      while( iarg <= *argc-1 )
      {
      if(!strcmp((*argv)[iarg],"-h") || !strcmp((*argv)[iarg],"-help"))
	{
          help_only=1;
          break;
	}
      if(!strcmp((*argv)[iarg],"-npmin"))
	{
/* IMB_3.0: Better arg checking for following cases */
          if( !IMB_chk_arg_int(NP_min,argv,argc,iarg+1) )
            {ok=-1;}
	  else if(*NP_min>0){n_cases -= 2;}
	  else
	    {ok=-1;}
          if( ok==-1 ) 
            { fprintf(stderr,"Invalid argument after \"npmin\"\n");
              break;
          }
          iarg++;
	}
      if(!strcmp((*argv)[iarg],"-multi"))
	{
          int tst;
          if( !IMB_chk_arg_int(&tst,argv,argc,iarg+1) )
            {ok=-1;}
          else if( tst==0 || tst==1 ){
              c_info->group_mode=tst;
              n_cases -= 2;
          }
	  else
	    {ok=-1;}
          if( ok==-1 ) 
            { fprintf(stderr,"Invalid argument after \"multi\"\n");
              break;
          }
          iarg++;
	}
/* IMB 3.1 << */
/* incorporation of flags -off_cache; -iter; -time; -mem */
      if(!strcmp((*argv)[iarg],"-off_cache"))
	{
          int ierr, cls;
          float cs;
          if( iarg+1>=*argc ) {
              fprintf(stderr,"Missing argument after \"off_cache\"\n");
              ok=-1;
              break;
          }
	  ierr=sscanf((*argv)[iarg+1],"%f,%d",&cs,&cls);
          if( ierr==1 ) 
           {
           if( cs<0. ) cs=CACHE_SIZE;
           cls=CACHE_LINE_SIZE;
           }
          else if( ierr!=2 )
           {
           fprintf(stderr,"Invalid off_cache selection\n");
           ok = -1;
           break;
           } 
	  ITERATIONS->cache_size = cs;
	  ITERATIONS->cache_line_size = cls;
          ITERATIONS->off_cache=1;
          n_cases -= 2;
          iarg++;
	}
      if(!strcmp((*argv)[iarg],"-iter"))
	{
          int ierr, msgs, overall_vol, msgs_nonaggr;
          if( iarg+1>=*argc ) {
              fprintf(stderr,"Missing argument after \"iter\"\n");
              ok=-1;
              break;
          }
	  ierr=sscanf((*argv)[iarg+1],"%d,%d,%d",&msgs,&overall_vol,&msgs_nonaggr);
          if( ierr<1 || ierr>3 )
           {
           fprintf(stderr,"Invalid iter selection\n");
           ok = -1;
           break;
           } 
          if(ierr>=1) 
           {
           ITERATIONS->msgspersample=msgs;
           }
          if(ierr>=2)
           {
           ITERATIONS->overall_vol=1024*1024*overall_vol;
           }
          if(ierr==3)
           {
           ITERATIONS->msgs_nonaggr=msgs_nonaggr;
           }
          n_cases -= 2;
          iarg++;
	}
      if(!strcmp((*argv)[iarg],"-time"))
	{
          int ierr; 
          float secs;
          if( iarg+1>=*argc ) {
              fprintf(stderr,"Missing argument after \"iter\"\n");
              ok=-1;
              break;
          }
	  ierr=sscanf((*argv)[iarg+1],"%f",&secs);
          if( ierr!=1 )
           {
           fprintf(stderr,"Invalid -time selection\n");
           ok = -1;
           break;
           } 
          ITERATIONS->iter_dyn=1;
          ITERATIONS->secs=secs;
          n_cases -= 2;
          iarg++;
	}
      if(!strcmp((*argv)[iarg],"-mem"))
	{
          int ierr; 
          float GB;
          if( iarg+1>=*argc ) {
              fprintf(stderr,"Missing argument after \"-mem\"\n");
              ok=-1;
              break;
          }
	  ierr=sscanf((*argv)[iarg+1],"%f",&GB);
          if( ierr!=1 )
           {
           fprintf(stderr,"Invalid -time selection\n");
           ok = -1;
           break;
           } 
          c_info->max_mem=GB;
          n_cases -= 2;
          iarg++;
	}
/* >> IMB 3.1  */
      if(!strcmp((*argv)[iarg],"-map"))
	{
          int ierr;
          if( iarg+1>=*argc ) {
              fprintf(stderr,"Missing argument after \"map\"\n");
              ok=-1;
              break;
          }
	  ierr=sscanf((*argv)[iarg+1],"%d%c%d",&c_info->px,&i,&c_info->py);
          if(ierr<3 || c_info->px*c_info->py < c_info->w_num_procs)
           {
           fprintf(stderr,"Invalid map selection\n");
           ok = -1;
           break;
           } 
          n_cases -= 2;
          iarg++;
	}
      if(!strcmp((*argv)[iarg],"-msglen"))
	{
	  FILE*t;
          if( !IMB_chk_arg_file(&t,argv,argc,iarg+1) )
            {ok=-1; 
             fprintf(stderr,"Filename after \"msglen\" flag invalid\n");
             break;}
          iarg_msg=iarg+1;
          n_cases -= 2;
          if( t )
          {
          char inp_line[72];
          while(fgets(inp_line,72,t))
          {
          if( inp_line[0] != '#' && strlen(inp_line)>1 )
          n_lens++;
          }
          fclose(t);
          }

          if ( n_lens==0 )
          {
          fprintf(stderr,"Sizes file %s invalid or doesnt exist\n",(*argv)[iarg_msg]);
          ok = -1;
          }
          iarg++;
	}
      if(!strcmp((*argv)[iarg],"-input"))
	{
	  FILE*t;
          if( !IMB_chk_arg_file(&t,argv,argc,iarg+1) )
            {ok=-1; 
             fprintf(stderr,"Filename after \"input\" flag invalid\n");
             break;}
          n_cases -= 2;
          if( t )
          {
          char inp_line[72];
          while(fgets(inp_line,72,t))
          {
          if( inp_line[0] != '#' && strlen(inp_line)>1 )
          n_cases++;
          }
          fclose(t);
          }
          iarg++;
	}
        iarg++;
       }

/* IMB_3.0 */
      if( !help_only ) {

      if(n_cases <= 0 )
        deflt = 1;
      else
        {
        iarg = 1;
 
        while( iarg <= *argc-1 )
        {
        if(!strcmp((*argv)[iarg],"-npmin")) 
                iarg++;
        else if(!strcmp((*argv)[iarg],"-multi")) 
                iarg++;
        else if(!strcmp((*argv)[iarg],"-msglen")) 
                iarg++;
/* IMB 3.1 << */
        else if(!strcmp((*argv)[iarg],"-off_cache")) 
                iarg++;
        else if(!strcmp((*argv)[iarg],"-iter")) 
                iarg++;
        else if(!strcmp((*argv)[iarg],"-time")) 
                iarg++;
        else if(!strcmp((*argv)[iarg],"-mem")) 
                iarg++;
/* >> IMB 3.1  */
        else if(!strcmp((*argv)[iarg],"-map")) 
                iarg++;
        else if(!strcmp((*argv)[iarg],"-input"))
	  {
	  FILE*t = fopen((*argv)[iarg+1],"r");
          if( t )
          {
          char inp_line[72], nam[32];
          while(fgets(inp_line,72,t))
          {
          if( inp_line[0] != '#' && strlen(inp_line)-1 )
            {
            sscanf(inp_line,"%s",nam);
            IMB_construct_blist(P_BList,n_cases,nam);
            }
          }
          fclose(t);
          }
          else fprintf(unit,"Input file %s doesnt exist\n",(*argv)[iarg+1]);
          iarg++;
          }
	else  
            {
              IMB_construct_blist(P_BList,n_cases,(*argv)[iarg]);          
            }
        iarg ++;
        }
        }
/* IMB_3.0 ; end "help_only" */
     }
    }

/* IMB_3.0 */
    if( help_only || ok<0 ) {

/* Set flag "not ok" => help mode in main */
    n_cases=0;
    IMB_i_alloc(&ALL_INFO,N_baseinfo,"Basic_Input");
    ok=-3;

    }
    else
    {

    if(deflt) {
      n_cases = 0;
      IMB_construct_blist(P_BList,0,"ALL");
               }

    if( iarg_msg>=0 )
       {
       FILE*t = fopen((*argv)[iarg_msg],"r");
       c_info->n_lens=n_lens;
       if( t && n_lens>0 )
             {
             char inp_line[72], S[32];
             int sz, isz;

             IMB_i_alloc(&c_info->msglen,n_lens,"Basic_Input");

             isz=-1;
             while(fgets(inp_line,72,t))
               {
               S[0]='\0';
               if( inp_line[0] != '#' && strlen(inp_line)-1 )
                 {
                 int ierr;
                 sz=0;
                 ierr=sscanf(&inp_line[0],"%d%s",&sz,&S[0]);
                 if( ierr<=0 || ierr==EOF || sz<0 )
                  {
                  ierr=-1;
                  }
                 else if(ierr==2  ) 
                  {
                 if      (S[0]=='k' ||  S[0]=='K') {sz=sz*1024;}
                 else if (S[0]=='m' ||  S[0]=='M') {sz=sz*1024*1024;}
                 else 
                   { ierr=-1; 
                   } 
                  } 
                 if( ierr>0 ) 
                   {
                   isz++;
                   c_info->msglen[isz]=sz;
                   }
                 else
                   {
                  fprintf(stderr,"Invalid line in file %s\n",(*argv)[iarg_msg]);
                   }
                 }
               }
               n_lens=c_info->n_lens=isz+1;
               fclose(t);
               if ( n_lens==0 )
               {
               fprintf(stderr,"Sizes File %s invalid or doesnt exist\n",(*argv)[iarg_msg]);
               ok = -1;
               }
          }
       }

    IMB_i_alloc(&ALL_INFO,N_baseinfo+n_cases,"Basic_Input");

    if( !deflt )
    {
    
    i=0;
    n_cases = 0;

    while( (*P_BList)[i].name )
      {
      int index;
      IMB_get_def_index(&index,(*P_BList)[i].name );
  
/* IMB_3.0
      if( index >= 0 )
*/
      if( index  != LIST_END )
                 ALL_INFO[N_baseinfo+n_cases++] = index;

      i++;
      }
    }

/* IMB_3.0 end "!help_only" */
    }

/* IMB 3.1 << */
    ALL_INFO[0] = *NP_min;
    ALL_INFO[1] = c_info->group_mode;
    ALL_INFO[2] = deflt;
    ALL_INFO[3] = ITERATIONS->cache_line_size;
    ALL_INFO[4] = ITERATIONS->msgspersample;
    ALL_INFO[5] = ITERATIONS->overall_vol;
    ALL_INFO[6] = ITERATIONS->msgs_nonaggr;
    ALL_INFO[7] = ITERATIONS->iter_dyn;
    ALL_INFO[8] = n_cases;
    ALL_INFO[9] = c_info->n_lens;
    ALL_INFO[10] = c_info->px;
    ALL_INFO[11] = c_info->py;
    ALL_INFO[12] = ok;

    ALL_F_INFO[0] = ITERATIONS->cache_size;
    ALL_F_INFO[1] = ITERATIONS->secs;
    ALL_F_INFO[2] = c_info->max_mem;

    MPI_Bcast(ALL_F_INFO,N_base_f_info,MPI_FLOAT,0,MPI_COMM_WORLD);
/* >> IMB 3.1  */
    MPI_Bcast(ALL_INFO,N_baseinfo,MPI_INT,0,MPI_COMM_WORLD);

    if( ok<0 ) return ok;

    if( n_cases > 0 && !deflt)
    MPI_Bcast(ALL_INFO+N_baseinfo,n_cases,MPI_INT,0,MPI_COMM_WORLD);

    if( n_lens  > 0 )
/* IMB 3.1 << */
    {
    MPI_Bcast(c_info->msglen,n_lens,MPI_INT,0,MPI_COMM_WORLD);
    if( ITERATIONS->iter_dyn )
     {
     IMB_i_alloc(&ITERATIONS->numiters,n_lens,"Basic_Input");
     }
/* >> IMB 3.1  */
    }

    IMB_v_free((void**)&ALL_INFO);

    }
    else  /* w_rank > 0 */
/* Receive input arguments */

    {
    int TMP[N_baseinfo];

/* IMB 3.1 << */
    MPI_Bcast(ALL_F_INFO,N_base_f_info,MPI_FLOAT,0,MPI_COMM_WORLD);
/* >> IMB 3.1  */
    MPI_Bcast(TMP,N_baseinfo,MPI_INT,0,MPI_COMM_WORLD);

    *NP_min = TMP[0];
    c_info->group_mode = TMP[1];
    deflt = TMP[2];
/* IMB 3.1 << */
    ITERATIONS->cache_size=ALL_F_INFO[0];
    if(ITERATIONS->cache_size<0.) ITERATIONS->off_cache=0;
    else                          ITERATIONS->off_cache=1;
    ITERATIONS->cache_line_size=TMP[3];
    ITERATIONS->msgspersample=TMP[4];
    ITERATIONS->overall_vol=TMP[5];
    ITERATIONS->msgs_nonaggr=TMP[6];
    ITERATIONS->iter_dyn=TMP[7];
    ITERATIONS->secs=ALL_F_INFO[1];
    c_info->max_mem=ALL_F_INFO[2];
    n_cases = TMP[8];
    n_lens = TMP[9];
    c_info->px = TMP[10];
    c_info->py = TMP[11];
    ok = TMP[12];
/* >> IMB 3.1  */

    if( ok<0 ) return ok;

    if( deflt )
      IMB_construct_blist(P_BList,0,"ALL");
    else if( n_cases>0 )
     {
     IMB_i_alloc(&ALL_INFO,n_cases,"Basic_Input");
     MPI_Bcast(ALL_INFO,n_cases,MPI_INT,0,MPI_COMM_WORLD);
     IMB_get_def_cases(&DEFC,&CMT);
     for( i = 0; i<n_cases; i++ )
/* IMB_3.0 */
     {
     if ( ALL_INFO[i] != LIST_INVALID ) {
     IMB_construct_blist(P_BList,n_cases,DEFC[ALL_INFO[i]]);
     }
     else {
     IMB_construct_blist(P_BList,n_cases,"");
     }
     }
     IMB_v_free((void**)&ALL_INFO);
     }
    else
     IMB_construct_blist(P_BList,1,"");

    if( n_lens>0 ) 
     {
     c_info->n_lens=n_lens;
     IMB_i_alloc(&c_info->msglen,n_lens,"Basic_Input");
     MPI_Bcast(c_info->msglen,n_lens,MPI_INT,0,MPI_COMM_WORLD);
/* IMB 3.1 << */
     if( ITERATIONS->iter_dyn )
     {
     IMB_i_alloc(&ITERATIONS->numiters,n_lens,"Basic_Input");
     }
/* >> IMB 3.1  */
     }

    }
#ifdef DEBUG
{
int i;
if( n_lens>0 )
{
fprintf(dbg_file,"Got msglen:\n");
for(i=0; i<n_lens; i++) fprintf(stderr,"%d ",c_info->msglen[i]);
}
fprintf(dbg_file,"\n\n");
fprintf(dbg_file,"px py = %d %d\n",c_info->px,c_info->py);
fprintf(dbg_file,"\n\n");
}
#endif
 
#ifndef EXT
    if( do_nonblocking )
    IMB_cpu_exploit(TARGET_CPU_SECS, 1);
#endif

return 0;
}


void IMB_get_rank_portion(int rank, int NP, int size, 
                          int unit_size, int* pos1, int* pos2)
/*

                      
                      Splits <size> into even contiguous pieces among processes
                      


Input variables: 

-rank                 (type int)                      
                      Process' rank
                      

-NP                   (type int)                      
                      Number of processes
                      

-size                 (type int)                      
                      Portion to split
                      

-unit_size            (type int)                      
                      Base unit for splitting
                      


Output variables: 

-pos1                 (type int*)
-pos2                 (type int*)                      
                      Process' portion is from unit pos1 to pos2
                      


*/
{

int ne, baslen, mod;

ne = (size+unit_size-1)/unit_size;
baslen = ne/NP;
mod    = ne%NP;

if( rank < mod )
  {
  *pos1 = rank*(baslen+1)*unit_size;
  *pos2 = *pos1-1+(baslen+1)*unit_size;
  }
  else
  {
  *pos1 = (rank*baslen + mod)*unit_size;
  *pos2 = *pos1-1 + baslen*unit_size;
  }

*pos2 = min(*pos2,size-1);

}

/********************************************************************/


int IMB_init_communicator(struct comm_info* c_info, int NP)
/*



Input variables: 

-NP                   (type int)                      
                      Number of all started processes
                      


In/out variables: 

-c_info               (type struct comm_info*)                      
                      Collection of all base data for MPI;
                      see [1] for more information
                      
                      Communicator of active processes gets initialized;
                      grouping of processes (in the 'multi' case) in communicators
                      


Return value          (type int)                      
                      Non currently used error exit (value is always 0)
                      


*/
{
int i,snd,cnt,proc,*aux_ptr;

MPI_Group group, w_group;
MPI_Status stat;

c_info->NP=NP;                     /* NUMBER OF OVERALL PROCESSES    */          
IMB_set_communicator( c_info );        /* GROUP MANAGEMENT               */

/* INITIALIZATION  WITHIN THE ACTUAL COMMUNICATOR */
if( c_info->communicator != MPI_COMM_NULL )
  {
    MPI_Comm_size(c_info->communicator,&(c_info ->num_procs));
    MPI_Comm_rank(c_info->communicator,&(c_info ->rank));
    
    c_info->pair0 = 0;
    c_info->pair1 = c_info ->num_procs-1;
    
    c_info->select_tag = 0;
    c_info->select_source = 0;
  }
else
  {
    c_info -> rank = -1;
  }

if( c_info->communicator == MPI_COMM_WORLD ) 
  {
    c_info->n_groups = 1;
    c_info->g_sizes[0] = c_info->w_num_procs;
    for(i=0; i<c_info->w_num_procs; i++) c_info->g_ranks[i]=i;
  }
else
  {
    /* Collect global group information */
    if( c_info->rank == 0 )
      {
	/* group leaders provide group ranks */
	MPI_Comm_group(MPI_COMM_WORLD,&w_group);
	MPI_Comm_group(c_info->communicator,&group);
	for (i=0; i<c_info->num_procs; i++) c_info->g_sizes[i] = i;

	/* TRANSLATION OF RANKS */
	MPI_Group_translate_ranks( group, c_info->num_procs, 
				   c_info->g_sizes,w_group,
				   c_info->g_ranks );
	snd = c_info->num_procs;
      }
    else
      {
	*c_info->g_ranks = -1;
	snd = 1;
      }
    /* w_rank 0 collects in g_ranks ranks of single groups */
    if( c_info->w_rank == 0 ) 
      {
        if( c_info->rank == 0 )
	  {
            c_info->n_groups = 1;
            c_info->g_sizes[c_info->n_groups-1] = c_info->num_procs;
            aux_ptr = c_info->g_ranks+c_info->num_procs;
	  }
	else
	  {
            c_info->n_groups = 0;
            aux_ptr=c_info->g_ranks;
	  }
	for( proc=1; proc<c_info->w_num_procs; proc++ )
	  {
	    /* Recv group ranks or -1  */
	    cnt = (int)(c_info->g_ranks+c_info->w_num_procs-aux_ptr);
/* July 2002 fix V2.2.1 (wrong logistics), next 23 lines */
	    if( cnt <= 0 )
	      /* all leaders have sent, recv dummies (-1) from others! */
	      {
		cnt=1;
	        MPI_Recv(&i,cnt,MPI_INT,proc,1000,MPI_COMM_WORLD,&stat);
	      }
	    else
              {

	        MPI_Recv(aux_ptr,cnt,MPI_INT,proc,1000,MPI_COMM_WORLD,&stat);
	    
	        if( *aux_ptr >= 0 ) 
	        {
		/* Message was from a group leader  */
		c_info->n_groups ++;
		MPI_Get_count( &stat, MPI_INT,
			       &c_info->g_sizes[c_info->n_groups-1]);
		aux_ptr += c_info->g_sizes[c_info->n_groups-1];
	        }

	      }
/* end fix V2.2.1 */
	  }
      }
    else  /* w_rank != 0 */
      {
	MPI_Send(c_info->g_ranks,snd,MPI_INT,0,1000,MPI_COMM_WORLD);
      }
  }
/* End collection of group information */   

IMB_set_errhand(c_info);

return 0;
}


/**********************************************************************/

void IMB_set_communicator(struct comm_info *c_info )
/*

                      
                      Performs the actual communicator splitting
                      


In/out variables: 

-c_info               (type struct comm_info *)                      
                      Collection of all base data for MPI;
                      see [1] for more information
                      
                      Application communicator gets initialized
                      


*/
{
  int color,key,i,j,ii;
  int* map;
  
  /* insert choice for communicator here;
     NOTE   :  globally more than one communicator is allowed   
     Example: grouping of pairs of processes: 
     0 0 1 1 2 2  .. (if even),  UNDEF 0 0 1 1 2 2  .. (if odd) 
     */

  if( c_info->communicator != MPI_COMM_NULL &&  
      c_info->communicator != MPI_COMM_SELF &&
      c_info->communicator != MPI_COMM_WORLD)
  {
  i=MPI_Comm_free(&c_info->communicator);
  IMB_err_hand(1,i);
  }

  IMB_i_alloc( &map, c_info->w_num_procs, "IMB_init");
  ii=0;
  if( c_info->px>1 && c_info->py>1 )
  {
  for( i=0; i<c_info->px; i++ )
  for( j=0; j<c_info->py; j++ )
    {
      if(i+j*c_info->px<c_info->w_num_procs)
        map[i+j*c_info->px] = ii++;
    }
  }
  else
  {
  for( i=0; i<c_info->w_num_procs; i++ ) map[i]=i;
  }

  if(c_info->group_mode >= 0)
    {
      i=map[c_info->w_rank];
      color = i/c_info->NP;
      c_info->group_no = color;
      key = i;
      if(color >= c_info->w_num_procs/c_info->NP) color=MPI_UNDEFINED;
      MPI_Comm_split(MPI_COMM_WORLD, color, key, &c_info->communicator);
    }
  /* Default choice and Group definition.  */
  else
    {
      if(map[c_info->w_rank] < c_info->NP) color=0;
      else color=MPI_UNDEFINED;   
      c_info->group_no = 0;
      key=map[c_info->w_rank];
      MPI_Comm_split(MPI_COMM_WORLD, color, key, &c_info->communicator); 
    }

    IMB_v_free((void**)&map);
}


int IMB_valid(struct comm_info * c_info, struct Bench* Bmark, int NP)
/*

                      
                      Validates an input Benchmark / NP setting
                      


Input variables: 

-c_info               (type struct comm_info *)                      
                      Collection of all base data for MPI;
                      see [1] for more information
                      

-Bmark                (type struct Bench*)                      
                      (For explanation of struct Bench type:
                      describes all aspects of modes of a benchmark;
                      see [1] for more information)
                      
                      User input benchmark setting
                      

-NP                   (type int)                      
                      Number of active processes
                      


Return value          (type int)                      
                      1/0 for valid / invalid input
                      


*/
{
/* Checks validity of Bmark for NP processes */
/* Erroneous cases: */
int invalid, skip;

invalid = 0; skip = 0;
#ifndef MPIIO
invalid = Bmark->RUN_MODES[0].type == SingleTransfer && NP <=1;
skip    = Bmark->RUN_MODES[0].type == SingleTransfer && NP > 2;
#endif

if ( invalid )
  {
  if( c_info->w_rank == 0 )
  {
  if( NP == 1 )
  fprintf(unit,"\n# !! Benchmark %s invalid for %d process   !! \n\n",Bmark->name,NP);
  else
  fprintf(unit,"\n# !! Benchmark %s invalid for %d processes !! \n\n",Bmark->name,NP);
  }
 
  return 0;
  }

/* Cases to skip: */
if ( skip ) return 0;

return 1;
}

void IMB_set_default(struct comm_info* c_info)
/*

                      
                      Default initialization of comm_info
                      


Output variables: 

-c_info               (type struct comm_info*)                      
                      Collection of all base data for MPI;
                      see [1] for more information
                      


*/
{
c_info->w_num_procs=0;          
c_info->w_rank=-1;
c_info->NP=0;                   
c_info->px=0;                   
c_info->py=0;                   
c_info->communicator=MPI_COMM_NULL;    
c_info->num_procs =0;
c_info->rank = -1;
c_info->s_data_type =  MPI_DATATYPE_NULL;
c_info->r_data_type =  MPI_DATATYPE_NULL;
c_info->red_data_type =  MPI_DATATYPE_NULL;
c_info->op_type = MPI_OP_NULL;
c_info->pair0 = c_info->pair1 = -2;
c_info->select_tag = 0;
c_info->select_source = 0;
c_info->s_buffer = NULL;
c_info->s_data = NULL;
c_info->s_alloc = 0;
c_info->r_buffer = NULL;
c_info->r_data = NULL;
c_info->r_alloc = 0;
/* IMB 3.1 << */
c_info->max_mem = MAX_MEM_USAGE;
/* >> IMB 3.1  */
c_info->n_lens = 0;
c_info->msglen = NULL;
c_info->group_mode = 0;
c_info->n_groups = 0;
c_info->group_no = -1;
c_info->g_sizes = NULL;
c_info->g_ranks = NULL;
c_info->reccnt = NULL;
c_info->rdispl = NULL;

c_info->ERR=MPI_ERRHANDLER_NULL;
 
#ifdef MPIIO
/*   FILE INFORMATION     */
 
c_info->filename=NULL;
c_info->File_comm=MPI_COMM_NULL;
c_info->File_num_procs=0;
c_info->all_io_procs=0;
c_info->File_rank=-1;

c_info->fh=MPI_FILE_NULL;
c_info->etype=MPI_DATATYPE_NULL;
c_info->e_size=0;
c_info->filetype=MPI_DATATYPE_NULL;

c_info->split.Locsize=0;
c_info->split.Offset=(MPI_Offset)0;
c_info->split.Totalsize=0;
 
c_info->amode=0;
c_info->info=MPI_INFO_NULL;
 
/* View: */
c_info->disp=(MPI_Offset)0;
c_info->datarep=NULL;
c_info->view=MPI_DATATYPE_NULL;
c_info->ERRF=MPI_ERRHANDLER_NULL;
#endif

#ifdef EXT
c_info->WIN=MPI_WIN_NULL;
c_info->info=MPI_INFO_NULL;
c_info->ERRW=MPI_ERRHANDLER_NULL;
#endif
 

}

/********************************************************************/

