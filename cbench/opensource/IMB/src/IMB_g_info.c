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
    
 File: IMB_g_info.c 

 Implemented functions: 

 IMB_general_info;
 IMB_make_sys_info;
 IMB_end_msg;

 ***************************************************************************/




char* VERSION="3.1";

#include <stdio.h>
#include <time.h>

#include "IMB_declare.h"
#include "IMB_benchmark.h"

#include "IMB_prototypes.h"

extern FILE* unit;




void IMB_general_info()
/*

                      
                      Prints to stdout some basic information 
                      (Version, time, system (see 'IMB_make_sys_info'))
                      


*/
{
  void IMB_make_sys_info();
  time_t T;
  
  time(&T);
  fprintf(unit,"#---------------------------------------------------\n");

#ifdef MPI1                 
  fprintf(unit,"#    Intel (R) MPI Benchmark Suite V%s, MPI-1 part    \n",VERSION);
#elif defined EXT
  fprintf(unit,"#    Intel (R) MPI Benchmark Suite V%s, MPI-2 part    \n",VERSION);
#elif defined MPIIO
  fprintf(unit,"#    Intel (R) MPI Benchmark Suite V%s, MPI-IO part   \n",VERSION);
#endif


  fprintf(unit,"#---------------------------------------------------\n");
  fprintf(unit,"# Date                  : %s",asctime(localtime(&T)));

  IMB_make_sys_info();
  fprintf(unit,"\n");
}

/* IMB 3.1 << */
/* include WIN case */
#ifndef WIN_IMB
#include <sys/utsname.h>
#else
#include <Windows.h>
#define INFO_BUFFER_SIZE 32767
#endif
/* >> IMB 3.1  */


void IMB_make_sys_info()
/*

                      
                      Prints to stdout some basic information about the system
                      (outcome of the 'uname' command)
                      


*/
{
  int dont_care, mpi_subversion, mpi_version;
/* IMB 3.1 << */
/* include WIN case */
#ifndef WIN_IMB
  struct utsname info;
  uname( &info );
  dont_care = MPI_Get_version(&mpi_version,&mpi_subversion);
  
  fprintf(unit,"# Machine               : %s\n",info.machine);
  fprintf(unit,"# System                : %s\n",info.sysname);
  fprintf(unit,"# Release               : %s\n",info.release);
  fprintf(unit,"# Version               : %s\n",info.version);
#else
  OSVERSIONINFO info;
  TCHAR infoBuf[INFO_BUFFER_SIZE];
  DWORD bufCharCount = INFO_BUFFER_SIZE;
  dont_care = MPI_Get_version(&mpi_version,&mpi_subversion);
  
  info.dwOSVersionInfoSize = sizeof(OSVERSIONINFO);
  GetVersionEx(&info);

  bufCharCount = ExpandEnvironmentStrings("%PROCESSOR_IDENTIFIER%",infoBuf,INFO_BUFFER_SIZE);

  fprintf(unit,"# Machine               : %s\n",infoBuf);

  if (info.dwMajorVersion == 4)
      switch (info.dwMinorVersion) {
      case 90 :
          fprintf(unit,"# System                : Windows Me\n");
          break;
      case 10 :
          fprintf(unit,"# System                : Windows 98\n");
          break;
      case 0 :
          fprintf(unit,"# System                : Windows NT 4.0\n");
          break;
      default :
          break;
      }
  else if (info.dwMajorVersion == 5)
      switch (info.dwMinorVersion) {
      case 2 :
          fprintf(unit,"# System                : Windows 2003\n");
          break;
      case 1 :
          fprintf(unit,"# System                : Windows XP\n");
          break;
      case 0 :
          fprintf(unit,"# System                : Windows 2000\n");
          break;
      default :
          break;
      }
  else if (info.dwMajorVersion == 6)
      switch (info.dwMinorVersion) {
      case 0 :
          fprintf(unit,"# System                : Windows Server \"Longhorn\"\n");
          break;
      default :
          break;
      }
  
  fprintf(unit,"# Release               : %-d.%-d.%-d\n",info.dwMajorVersion,
          info.dwMinorVersion,info.dwBuildNumber);
  fprintf(unit,"# Version               : %s\n",info.szCSDVersion);
#endif
/* >> IMB 3.1  */
  fprintf(unit,"# MPI Version           : %-d.%-d\n",mpi_version,mpi_subversion);
  fprintf(unit,"# MPI Thread Environment: ");

  switch (mpi_thread_environment) {
  case MPI_THREAD_SINGLE :
    fprintf(unit,"MPI_THREAD_SINGLE\n");
    break;
  case MPI_THREAD_FUNNELED :
    fprintf(unit,"MPI_THREAD_FUNNELED\n");
    break;
  case MPI_THREAD_SERIALIZED :
    fprintf(unit,"MPI_THREAD_SERIALIZED\n");
    break;
  default :
    fprintf(unit,"MPI_THREAD_MULTIPLE\n");
    break;
  }
}

void IMB_end_msg(struct comm_info* c_info )
/*

                      
                      Prints to stdout an eventual end message (currently empty)
                      


Input variables: 

-c_info               (type struct comm_info*)                      
                      Collection of all base data for MPI;
                      see [1] for more information
                      


*/
{

FILE* u;

if( c_info->w_rank == 0 ) {

for( u=stdout; u; u=(u==unit ? NULL : unit) )
{

}


}

}
