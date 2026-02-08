include ../../make.def

export CFLAGS

SRC=phloem-1.0.0
TAR=phloem_v1.0.tgz
URL=https://asc.llnl.gov/sequoia/benchmarks/$(TAR)

# I'm not sure why the following EXECS specification seems to now be causing
# 'install' trouble. I just replaced it with the shell expanded version but
# keeping the original line for reference
#EXECS = $(SRC)/linktest*/linux/linktest $(SRC)/presta*/com $(SRC)/sqmr*/sqmr $(SRC)/torustest*/linux/{torustest,generate} $(SRC)/mpiGraph*/{mpiGraph,crunch_mpiGraph} $(SRC)/mpiBench*/{mpiBench_Allreduce,mpiBench_Barrier,mpiBench_Bcast,crunch_mpiBench}
EXECS = $(SRC)/linktest-1.0.0/linux/linktest $(SRC)/presta-1.0.0/com $(SRC)/sqmr-1.0.0/sqmr $(SRC)/torustest-1.0.0/linux/torustest $(SRC)/torustest-1.0.0/linux/generate $(SRC)/mpiGraph-1.0.0/mpiGraph $(SRC)/mpiGraph-1.0.0/crunch_mpiGraph $(SRC)/mpiBench-1.0.0/mpiBench_Allreduce $(SRC)/mpiBench-1.0.0/mpiBench_Barrier $(SRC)/mpiBench-1.0.0/mpiBench_Bcast $(SRC)/mpiBench-1.0.0/crunch_mpiBench
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

CFLAGS += -DPRINT_ENV

default all normal: .make-$(SRC)

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	@[ -d $@ ] && touch $@

.make-$(SRC): $(SRC)
	$(MAKE) CC=$(CC) -C src > .make-$(SRC) 2>&1
	@touch $@

clean:
	[ -d $(SRC) ] && $(MAKE) -C $(SRC) clean || :

distclean:
	/bin/rm -rf $(SRC) $(TAR) src .make-$(SRC)

install uninstall: default
	$(do-$@)
