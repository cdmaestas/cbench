Intel(R) MPI Benchmarks

Version 3.1
Release Notes

====================================================================

Main changes vs. IMB_3.0:

The changes vs. the previous version, 3.0, are new benchmarks, new flags and a
Windows version of IMB 3.1.
As to the new control flags, most important are

- a better control of the overall repetition counts, run time and memory exploitation
- facility to avoid cache re-usage of message buffers as far as possible

New benchmarks
--------------

The 4 benchmarks
-	Gather
-	Gatherv
-	Scatter
-	Scatterv
were added and are to be used in the usual IMB style.

New command line flags for better control
-----------------------------------------

The 4 flags added are 
-off_cache,  -iter, -time, -mem 

-off_cache: 
when measuring performance on high speed interconnects or, in particular,
across the shared memory within a node, traditional IMB results eventually
included a very beneficial cache re-usage of message buffers which led to
idealistic results. The flag -off_cache allows for (largely) avoiding cache
effects and lets IMB use message buffers which are very likely not resident
in cache.

-iter, -time:
are there for enhanced control of the overall run time, which is crucial for
large clusters, where collectives tend to run extremely long in traditional
IMB settings.

-mem
is used to determine an a priori maximum (per process) memory usage of IMB for
the overall message buffers.

Windows version
---------------
The three Intel MPI Benchmarks have been ported to Microsoft Windows*.

For Microsoft Windows systems, the makefiles are called Makefile and
make_ict_win and they are based on "nmake" syntax.

To get help in building the three benchmark executables on Microsoft
Windows, simply type nmake within the src directory of the IMB 3.1
installation.

For Linux* systems, the makefiles are called GNUmakefile, make_ict,
and make_mpich.

To get help in building the three benchmark executables on Linux,
simply type gmake within the src directory of the IMB 3.1 installation.

Miscellaneous changes
----------------------

- in the "Exchange" benchmark, the 2 buffers sent by MPI_Isend are separate now

- the command line is repeated in the output

- memory management is now completely encapsulated in functions "IMB_v_alloc / IMB_v_free"


====================================================================

Version 3.0
Release Notes

====================================================================

Main changes vs. IMB_2.3:

- Benchmark "Alltoallv" added
- Flag -h[elp] added for help
- All except 2 makefiles erased
- Better argument line error handling

====================================================================

This document contains the description of the software package
(installation, running, header files and data structures, interfaces
of all functions in IMB). 

For a documentation of the methodologies behind it, see the reference

[1] doc/IMB_ug-3.1.pdf


Overview
========

I.   Installing and running IMB
II.  Header files, struct data types
III. All interfaces and brief documentation

I. Installing and running IMB
=============================

I.1 Directory
-------------

After unpacking, the directory contains

ReadMe_first

and 4 subdirectories

./doc  (this file; IMB.pdf, the methodology description)
./src  (program source- and Make-files)
./license (license agreement text)
./versions_news (version history and news)

>>>>
Please read the license agreements first:
  - license.txt specifies the source code license granted to you
  - use-of-trademark-license.txt specifies the license for using the 
    name and trademark "Intel(R) MPI Benchmarks"
  - Copyright (c) 2003-2007, Intel Corporation. All rights reserved. 
    *Other brands and names are the property of their respective owners
<<<<


I.2 Installation and quick start
--------------------------------

(please read [1] for more extensive explanations).

3 Makefiles are provided:

make_ict   (for Intel Cluster Tools usage on Linux*)
make_mpich (for mpich; has to be edited on Linux*)
make_ict_win (for Intel Cluster Tools usage on Microsoft Windows*)

, invoked by

gmake -f make_ict <target>
gmake -f make_mpich <target>
nmake -f make_ict_win <target>

(attention: in contrast to IMB_2.3, these are full makefiles
and don't need to included)

In their header, variables are set:

Mandatory:

CC          = mpicc (e.g.)
CLINKER     = ${CC} (e.g.)

Optional:

MPI_INCLUDE =
LIB_PATH    =
LIBS        = 
OPTFLAGS    = 
LDFLAGS     =
CPPFLAGS    = 

These variables are then exported to the main part of the Makefile,
Makefile.base.

In make_mpich, the root of the installation must be set:

MPI_HOME=/opt/mpich2-1.0.3-icc.icpc-ifort/ch3_ssm


In the end, compilation will follow the rule

	$(CC) $(MPI_INCLUDE) $(CPPFLAGS) $(OPTFLAGS) -c $*.c

and linkage is done by

	$(CLINKER) $(LDFLAGS) -o <exe> <objects>  $(LIB_PATH) $(LIBS)

The only CPPFLAGS setting currently provided is "-DCHECK"; when activated,
IMB checks contents of message passing buffers, as far as possible. Should
be used for correctness check of an implementation only, not for 
performance measurements.

make -f <choice> IMB-<case>, where case is

"MPI1", "EXT" or "MPIIO"


I.3 Running and run time flags
------------------------------

Calling sequence (command line will be repeated in Output table!):
 
 
IMB-MPI1    [-h{elp}]
            [-npmin     <NPmin>]
            [-multi     <MultiMode>]
            [-off_cache <cache_size[,cache_line_size]>
            [-iter      <msgspersample[,overall_vol[,msgs_nonaggr]]>
            [-time      <max_runtime per sample>]
            [-mem       <max. per process memory for overall message buffers>]
            [-msglen    <Lengths_file>]
            [-map       <PxQ>]
            [-input     <filename>]
            [benchmark1 [,benchmark2 [,...]]]
 
where 
 
- h ( or help) just provides basic help 
  (if active, all other arguments are ignored)
 
- npmin
 
  the argument after npmin is NPmin, 
  the minimum number of processes to run on
  (then if IMB is started on NP processes, the process numbers 
   NPmin, 2*NPmin, ... ,2^k * NPmin < NP, NP are used)
   >>>
   to run on just NP processes, run IMB on NP and select -npmin NP
   <<<
  default: 
  NPmin=2
 
- off_cache
 
  the argument after off_cache can be 1 single (cache_size) 
  or 2 comma separated (cache_size,cache_line_size) numbers
  
  cache_size is a float for the size of the last level cache in MBytes
  can be an upper estimate (however, the larger, the more memory is exploited)
  can be -1 to use the default in => IMB_mem_info.h
  
  cache_line_size is optional as second number (int), 
  size (Bytes) of a last level cache line, can be an upper estimate 
  any 2 messages are separated by at least 2 cache lines 
  the default is set in => IMB_mem_info.h
   
  remark: -off_cache is effective for IMB-MPI1, IMB-EXT, but not IMB-IO 
  
  examples 
   -off_cache -1 (use defaults of IMB_mem_info.h); 
   -off_cache 2.5 (2.5 MB last level cache, default line size); 
   -off_cache 16,128 (16 MB last level cache, line size 128); 
  
  default: 
  no cache control, data likely to come out of cache most of the time 
 
- iter 
 
  the argument after -iter can be 1 single, 2 comma separated, or 3 comma
separated 
  integer numbers, which override the defaults 
  MSGSPERSAMPLE, OVERALL_VOL, MSGS_NONAGGR of =>IMB_settings.h 
  examples 
   -iter 2000        (override MSGSPERSAMPLE by value 2000) 
   -iter 1000,100    (override OVERALL_VOL by 100) 
   -iter 1000,40,150 (override MSGS_NONAGGR by 150) 
  
  default: 
  iteration control through parameters MSGSPERSAMPLE,OVERALL_VOL,MSGS_NONAGGR
=> IMB_settings.h 
 
- time
 
  the argument after -time is a float, specifying that 
  a benchmark will run at most that many seconds per message size 
  the combination with the -iter flag or its defaults is so that always 
  the maximum number of repetitions is chosen that fulfills all restrictions 
  example 
   -time 0.150       (a benchmark will (roughly) run at most 150 milli seconds
per message size, iff
                      the default (or -iter selected) number of repetitions
would take longer than that) 
  
  remark: per sample, the rough number of repetitions to fulfill the -time
request 
          is estimated in preparatory runs that use ~ 1 second overhead 
  
  default: 
  no time limit 
 
- mem
 
  the argument after -mem is a float, specifying that 
  at most that many GBytes are allocated per process for the message buffers 
  if the size is exceeded, a warning will be output, stating how much memory 
  would have been necessary, but the overall run is not interrupted 
  example  
   -mem 0.2         (restrict memory for message buffers to 200 MBytes per
process) 
  
  default: 
  the memory is restricted by MAX_MEM_USAGE => IMB_mem_info.h 
 
- map
 
  the argument after -map is PxQ, P,Q are integer numbers with P*Q <= NP
  enter PxQ with the 2 numbers separated by letter "x" and no blancs
  the basic communicator is set up as P by Q process grid
 
  if, e.g., one runs on N nodes of X processors each, and inserts
  P=X, Q=N, then the numbering of processes is "inter node first"
  running PingPong with P=X, Q=2 would measure inter-node performance
  (assuming MPI default would apply 'normal' mapping, i.e. fill nodes
  first priority) 
 
  default: 
  Q=1
 
- multi
 
  the argument after -multi is MultiMode (0 or 1)
 
  if -multi is selected, running the N process version of a benchmark
  on NP overall, means running on (NP/N) simultaneous groups of N each.
 
  MultiMode only controls default (0) or extensive (1) output charts.
  0: only lowest performance groups is output
  1: all groups are output
 
  default: 
  multi off
 
- msglen
 
  the argument after -msglen is a lengths_file, an ASCII file, containing any
set of nonnegative
  message lengths, 1 per line
 
  default: 
  no lengths_file, lengths defined by settings.h, settings_io.h
  
- input
 
  the argument after -input is a filename is any text file containing, line by
line, benchmark names
  facilitates running particular benchmarks as compared to using the
  command line.
 
  default: 
  no input file exists
  
- benchmarkX is (in arbitrary lower/upper case spelling)

for case==MPI1 one of
 
PingPong
PingPing
Sendrecv
Exchange
Bcast
Allgather
Allgatherv
Gather
Gatherv
Scatter
Scatterv
Alltoall
Alltoallv
Reduce
Reduce_scatter
Allreduce 
Barrier

for case==EXT one of

Window
Unidir_Put
Unidir_Get
Bidir_Get
Bidir_Put
Accumulate

for case==IO one of

S_Write_indv
S_Read_indv
S_Write_expl
S_Read_expl
P_Write_indv
P_Read_indv
P_Write_expl
P_Read_expl
P_Write_shared
P_Read_shared
P_Write_priv
P_Read_priv
C_Write_indv
C_Read_indv
C_Write_expl
C_Read_expl
C_Write_shared
C_Read_shared


IMB will run the benchmarks corresponding to well defined rules [1]. The
run settings (message lengths, in particular) are fixed in the header files 
(see next section) 

settings.h (for MPI1, EXT cases) and settings_io.h (for IO).

These should not normally be changed to achieve unified rules. But, they
might be modified when special cases need to be looked at.





II.  Header files, struct data types
====================================

THe following header files belong the the code:

IMB_settings.h
IMB_settings_io.h

IMB_prototypes.h

IMB_benchmark.h
IMB_bnames_ext.h
IMB_bnames_io.h
IMB_bnames_mpi1.h

IMB_comm_info.h

IMB_declare.h
IMB_comments.h
IMB_appl_errors.h
IMB_mem_info.h
IMB_err_check.h

All header files contain inline documentation, so here only brief
hints are given.

II.1 IMB_settings.h / IMB_settings_io.h
-------------------------------------------
These files fix the run mode of IMB, in particular the message lengths
each benchmark will use. Normally, these should not be changed.


All other headers are IMB internal and must not normally be changed. 
Only for detailed understanding of the code, it is necessary to look
at these files.

II.2. IMB_prototypes.h
------------------------
Collection of all prototypes use in IMB

II.3. IMB_benchmark.h
------------------------
IMB sets up a linked list of benchmarks requested by the user. The description
of a benchmark is collected in a "struct Bench" data structure which is 
defined here. In particular contains a benchmark structure the 'modes' 
(sub-structure 'MODES') of a benchmark which says whether the benchmark is

- single/parallel/collective transfer or synchronisation
- aggregate/non aggregate (only EXT and MIPIO)
- blocking/nonblocking

(see the manual).

This structure "MODES" is also used for the => calling sequences of the benchmarks.

II.4. IMB_bnames_<case>.h
-------------------------

Internal string lists of benchmark names

II.5. IMB_comm_info.h
---------------------

Collection of all (run time dependent) data describing the MPI environment of
a calling process (communicators, process ids etc).

II.6. IMB_declare.h
---------------------
Declaration of global variables and preprocessor macros.

II.7. IMB_mem_info.h
---------------------
Declaration of memory usage parameters

II.8. IMB_comments.h
---------------------
(Currently empty) list of comments attached to each benchmark

II.9. IMB_appl_errors.h, IMB_err_check.h
----------------------------------------
Definition of internal error codes and callback functions for error handlers.



III.  Interfaces with brief documentation
=========================================

The code consists of the following (41) C modules, which in
turn contain several functions eventually.

IMB_allgather.c
IMB_allgatherv.c
IMB_scatter.c
IMB_scatterv.c
IMB_gather.c
IMB_gatherv.c
IMB_allreduce.c
IMB_alltoall.c
IMB_barrier.c
IMB_bcast.c
IMB_benchlist.c
IMB.c
IMB_chk_diff.c
IMB_cpu_exploit.c
IMB_declare.c
IMB_err_handler.c
IMB_exchange.c
IMB_g_info.c
IMB_init.c
IMB_init_file.c
IMB_init_transfer.c
IMB_mem_manager.c
IMB_ones_accu.c
IMB_ones_bidir.c
IMB_ones_unidir.c
IMB_open_close.c
IMB_output.c
IMB_parse_name_ext.c
IMB_parse_name_io.c
IMB_parse_name_mpi1.c
IMB_pingping.c
IMB_pingpong.c
IMB_read.c
IMB_reduce.c
IMB_reduce_scatter.c
IMB_sendrecv.c
IMB_strgs.c
IMB_user_set_info.c
IMB_warm_up.c
IMB_window.c
IMB_write.c
