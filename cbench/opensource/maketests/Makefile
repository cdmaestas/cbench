include $(CBENCHOME)/make.def

# vim: syntax=make

TESTS = dummy_blas dummy_lapack dummy_fftw dummy_blas_fftw 

all: $(TESTS) linkstatus

dummy_blas: dummy.c
	@echo "===== Testing BLAS linkage ===="
	$(CC) -DBLAS $(CFLAGS) -c -o $@.o $<
	$(CC) $@.o $(BLASLIB) -o $@
	@echo;echo

dummy_fftw: dummy.c
	@echo "===== Testing FFTW linkage ===="
	$(CC) -DFFTW $(FFTWINCLUDE) $(CFLAGS) -c -o $@.o $<
	$(CC) $@.o $(FFTWLIB) -o $@
	@echo;echo

dummy_blas_fftw: dummy.c
	@echo "===== Testing BLAS+FFTW linkage ===="
	$(CC) -DBLAS -DFFTW  $(FFTWINCLUDE) $(CFLAGS) -c -o $@.o $<
	$(CC) $@.o $(FFTWLIB) $(BLASLIB)  -o $@
	@echo;echo

# LAPACK requires BLAS by design
dummy_lapack: dummy.c
	@echo "===== Testing LAPACK linkage ===="
	$(CC) -DLAPACK $(CFLAGS) -c -o $@.o $<
	$(CC) $@.o $(LAPACKLIB) $(BLASLIB) -o $@
	@echo;echo


clean distclean:
	/bin/rm -f *.o  $(TESTS)


srcsubdir := $(notdir $(shell pwd))
linkstatus:
	@for tgtbin in $(TESTS); do \
		if [ ! -x $$tgtbin ]; then \
			tput setaf 1 ; tput bold ; \
			echo "LINKTEST: $$tgtbin was not built" ; \
			tput sgr0 ;\
		else \
			tput setaf 2 ; tput bold ; \
			echo "LINKTEST: $$tgtbin was built ok" ; \
			tput sgr0 ;\
		fi; \
	done


