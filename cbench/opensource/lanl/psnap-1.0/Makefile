include $(CBENCHOME)/make.def

#CC=mpicc

#MPIINCLUDE=-I/usr/local/openmpi-1.0.1/include
#MPILIBS=-L/usr/local/openmpi-1.0.1/lib -lmpi

#CFLAGS=-O3 $(MPIINCLUDE)
#CFLAGS+=-DUSE_GETTIMEOFDAY
LDLIBS=$(MPILIBS) -lm

psnap: psnap.c
	$(CC) $(CFLAGS) $(LDFLAGS) psnap.c $(LDLIBS) -o $@

clean:
	rm -f psnap psnap.ch_shmem *.o
