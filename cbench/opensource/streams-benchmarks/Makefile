include ../../make.def

VERSION=5.9
SRC=streams
FILES=stream.c mysecond.c stream.f stream.c.5.10
URL=http://www.cs.virginia.edu/stream/FTP/Code
MPIURL=http://www.cs.virginia.edu/stream/FTP/Code/Versions/stream_mpi.f

EXEC = stream_f-$(VERSION) stream_c-$(VERSION) stream_mpi
INSTALLDIR = $(hwtest_bin_dir)
INSTALLTARGETS = $(EXEC)

default: $(EXEC)

download: $(SRC)

$(SRC): stream_mpi.f mysecond.c stream.c stream.f

stream_mpi.f:
	@[ ! -f $@ ] && curl -k --connect-timeout 10 --retry 2 -L -O $(MPIURL)

mysecond.c stream.c stream.f stream.c.5.10: 
	@[ ! -f $@ ] && curl -k --connect-timeout 10 --retry 2 -L -O $(URL)/$@

mysecond.o: mysecond.c
	$(PLAINCC) $(CCFLAGS) -c mysecond.c
	@touch $@

stream_mpi: stream_mpi.f mysecond.o
	$(F90) $(FFLAGS) -c stream_mpi.f
	$(F90) $(FFLAGS) stream_mpi.o mysecond.o -o stream_mpi

stream_f-$(VERSION): stream.f mysecond.o
	$(PLAINF77) $(FFLAGS) -c stream.f
	$(PLAINF77) $(FFLAGS) stream.o mysecond.o -o stream_f-$(VERSION)

stream_c-$(VERSION): stream.c
	$(PLAINCC) $(CCFLAGS) stream.c -o stream_c-$(VERSION)

stream_c_5_10: stream.c.5.10
	[ -f stream.c.5.10 ] && ln -sf stream.c.5.10 stream_5_10.c
	$(PLAINCC) $(CCFLAGS) stream_5_10.c -o stream_c.5.10

.make-$(SRC): $(EXEC)
	touch $@

clean: 
	rm -f mysecond.o  stream_c-$(VERSION)  stream_f-$(VERSION)  stream.o .make-$(SRC) stream_mpi stream_mpi.o

distclean: clean
	rm -f $(FILES) .make-$(SRC) stream_5_10.c stream_mpi.f


install uninstall: default
	$(do-$@)
