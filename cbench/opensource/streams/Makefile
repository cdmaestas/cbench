include ../../make.def

INSTALLDIR = $(hwtest_bin_dir)
INSTALLTARGETS = stream-* stream2-* stream-mpi

FLAGS = $(CFLAGS)
FFLAGS += $(OPTFLAGS)
MYSECOND=mysecond.o

EXECS = stream-c stream-f stream2-f stream-big-c stream-mpi stream-big-f stream-mpi stream-big-10G-c

ifeq ($(COMPILER),intel)
  EXECS += stream-intel-c stream-intel-f stream-intel2-c stream-intel2-f stream-intel3-f stream-intel-openmp-f stream-intel-openmp-c stream-intel2-openmp-f stream-intel2-openmp-c stream-mpi-openmp
endif
ifeq ($(COMPILER),gcc)
  EXECS += stream-gcc-c stream-gcc2-c stream-gcc5-c stream-gcc6-c stream-gcc7-c
endif
ifeq ($(COMPILER),pgi)
  EXECS += stream-pgi-c stream-pgi2-c stream-pgi-f stream-pgi2-f stream-pgi3-f stream-pgi-openmp-f stream-pgi2-openmp-f stream-pgi3-openmp-f stream-pgi-openmp-c stream-pgi2-openmp-c stream-pgi3-openmp-c stream-pgi4-openmp-c stream-pgi4-openmp-f
endif

default: all

MPICH_CH = ch_shmem
ifeq ($(CBENCH_STANDALONE),yes)
  $(warning ================ STANDALONE MPI COMPILE)
  EXECS = stream-mpi.$(MPICH_CH)
  MPIHOME = $(CBENCHOME)/opensource/mpich
  INSTALLTARGETS = $(EXECS)
default: stream-mpi.$(MPICH_CH)
endif

all: $(EXECS)

download:

stream-c: stream.c
	$(PLAINCC) $(FLAGS) -o $@ $^ -lm

stream-f: stream.f mysecond.o
	$(FORT) $(FFLAGS) -o $@ $^ -lm

stream2-f: stream2.f mysecond.o
	$(FORT) $(FFLAGS) -o $@ $^ -lm

stream-mpi: stream_mpi.f $(MYSECOND)
	$(F90) $(FFLAGS) -o $@ $^

stream-mpi.$(MPICH_CH): stream-mpi
	/bin/mv -f  stream-mpi stream-mpi.$(MPICH_CH)

stream-big-c: stream_big.c
	$(PLAINCC) $(FLAGS) -o $@ $^ -lm

stream-big-f: stream_big.f mysecond.o
	$(F90) $(FFLAGS) -o $@ $^ -lm

stream-big-10G-c: stream_10G.c
	$(PLAINCC) $(FLAGS) -mcmodel=medium -o $@ $^ -lm

# stream binary optimized for GCC compilers
stream-gcc-c: stream_big.c
	$(PLAINCC) $(COMMON_FLAGS) -O3 -mtune=nocona -o $@ $^ -lm
stream-gcc2-c: stream_big.c
	$(PLAINCC) $(COMMON_FLAGS) -O3 -mtune=opteron -o $@ $^ -lm
stream-gcc5-c: stream_big.f mysecond.o
	$(PLAINF90) $(COMMON_FLAGS) -O3 -mtune=opteron -o $@ $^ -lm
stream-gcc6-c: stream_big.f mysecond.o
	$(PLAINF77) $(COMMON_FLAGS) -O3 -mtune=nocona -o $@ $^ -lm
stream-gcc7-c: stream_big.f mysecond.o
	$(PLAINF77) $(COMMON_FLAGS) -O3 -mtune=amdfam10 -funroll-all-loops -o $@ $^ -lm

# stream binaries optimized for Intel compilers
stream-intel-c: stream_big.c
	$(PLAINCC) $(COMMON_FLAGS) -O3 -axP -ip -fno-alias -o $@ $^ -lm
stream-intel2-c: stream_big.c
	$(PLAINCC) $(COMMON_FLAGS) -O3 -axW -ip -fno-alias -o $@ $^ -lm
stream-intel-f: stream_big.f mysecond.o
	$(PLAINF77) $(COMMON_FLAGS) -O3 -axP -ip -fno-alias -o $@ $^ -lm
stream-intel2-f: stream_big.f mysecond.o
	$(PLAINF77) $(COMMON_FLAGS) -O3 -axW -ip -fno-alias -o $@ $^ -lm
stream-intel3-f: stream_big.f mysecond.o
	$(PLAINF77) $(COMMON_FLAGS) -O3 -axsse4.2 -ip -fno-alias -o $@ $^ -lm
stream-intel-openmp-f: stream.f mysecond.o
	$(PLAINF77) $(COMMON_FLAGS) -O3 -ip -openmp -fno-alias -o $@ $^ -lm
stream-intel2-openmp-f: stream_big.f mysecond.o
	$(PLAINF77) $(COMMON_FLAGS) -O3 -ip -openmp -fno-alias -o $@ $^ -lm
stream-intel-openmp-c: stream.c
	$(PLAINCC) $(COMMON_FLAGS) -O3 -ip -openmp -fno-alias -o $@ $^ -lm
stream-intel2-openmp-c: stream_big.c
	$(PLAINCC) $(COMMON_FLAGS) -O3 -ip -openmp -fno-alias -o $@ $^ -lm

# stream binaries optimized for PGI compilers
stream-pgi-c: stream_big.c
	$(PLAINCC) $(COMMON_FLAGS) -O3 -fast -Mipa=fast -tp=x64 -o $@ $^ 
stream-pgi2-c: stream_big.c
	$(PLAINCC) $(COMMON_FLAGS) -O3 -fast -Mipa=fast -tp=k8-64e -o $@ $^ 
stream-pgi-f: stream_big.f mysecond.o
	$(PLAINF77) $(COMMON_FLAGS) -O3 -fast -Mipa=fast -tp=x64 -o $@ $^ -lm
stream-pgi2-f: stream_big.f mysecond.o
	$(PLAINF77) $(COMMON_FLAGS) -O3 -fast -Mipa=fast -tp=k8-64e -o $@ $^ -lm
stream-pgi3-f: stream_big.f mysecond.o
	$(PLAINF77) $(COMMON_FLAGS) -O3 -fast -Mipa=fast -tp=barcelona-64 -Msmartalloc -o $@ $^ -lm
stream-pgi-openmp-f: stream.f mysecond.o
	$(PLAINF77) $(COMMON_FLAGS) -O3 -fast -Mipa=fast -mp -o $@ $^ -lm
stream-pgi2-openmp-f: stream_big.f mysecond.o
	$(PLAINF77) $(COMMON_FLAGS) -O3 -fast -Mipa=fast -mp -o $@ $^ -lm
stream-pgi3-openmp-f: stream_big.f mysecond.o
	$(PLAINF77) $(COMMON_FLAGS) -O3 -fast -Mipa=fast -mp=numa -o $@ $^ -lm
#  LLNL streams setup
stream-pgi4-openmp-f: stream_big.f mysecond.o
	$(PLAINF77) $(COMMON_FLAGS) -O3 -fastsse -Msmart -Mcache_align -Mvect=sse -Mnontemporal -Munsafe_par_align -mp=align -o $@ $^ -lm
stream-pgi-openmp-c: stream.c
	$(PLAINCC) $(COMMON_FLAGS) -O3 -fast -Mipa=fast -mp -o $@ $^ 
stream-pgi2-openmp-c: stream_big.c
	$(PLAINCC) $(COMMON_FLAGS) -O3 -fast -Mipa=fast -mp -o $@ $^ 
stream-pgi3-openmp-c: stream_big.c
	$(PLAINCC) $(COMMON_FLAGS) -O3 -fast -Mipa=fast -mp=numa -o $@ $^ -lm
#  LLNL streams setup
stream-pgi4-openmp-c: stream_big.c
	$(PLAINCC) $(COMMON_FLAGS) -O3 -fastsse -Mcache_align -Mvect=sse -Msmart -Mnontemporal -Munsafe_par_align -mp -o $@ $^ -lm




mysecond.o: mysecond.c
	$(PLAINCC) $(FLAGS) -o $@ -DUNDERSCORE -c $<


clean:
	rm -f stream-* stream2-* $(MYSECOND) $(MYSECOND_CC) *.o *.oo

distclean: clean

install uninstall: default
	$(do-$@)
