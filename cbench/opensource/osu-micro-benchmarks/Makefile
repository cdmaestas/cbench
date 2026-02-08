include ../../make.def

VERSION=4.1
SRC=osu-micro-benchmarks-$(VERSION)
TAR=$(SRC).tar.gz
URL="http://mvapich.cse.ohio-state.edu/benchmarks/$(TAR)"
EXEC:=osu_acc_latency osu_bcast osu_bw osu_get_latency osu_latency_mt osu_multi_lat osu_passive_get_bw osu_passive_put_bw osu_put_bibw osu_put_latency osu_alltoall osu_bibw osu_get_bw osu_latency osu_mbw_mr osu_passive_acc_latency osu_passive_get_latency osu_passive_put_latency osu_put_bw

INSTALLDIR = $(bin_dir)
INSTALLTARGETS = 

default: .make-$(SRC)

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	@[ -d $@ ] && touch $@

.configure-$(SRC): $(SRC)
	@echo "Configuring $(SRC)"
	cd src && ./configure CC=$(CC) --prefix=$(CBENCHTEST)/$(SRC) > ../.configure-$(SRC) 2>&1
	@touch $@

.make-$(SRC): .configure-$(SRC)
	@echo "Compiling $(SRC)"
	$(MAKE) -C src CC=$(CC) > .make-$(SRC) 2>&1; touch .configure-$(SRC)
	@touch $@

clean:
	@if [ -f src/Makefile ] ; then $(MAKE) -C src clean > .make-$(SRC) 2>&1; fi
	rm -f .make-$(SRC) .configure-$(SRC)

distclean:
	rm -fr .make-$(SRC) .configure-$(SRC) src $(TAR) $(SRC)

install: .make-$(SRC)
	@echo "Installing $(SRC)"
	cd src && make install >> ../.make-$(SRC) 2>&1
	mkdir -p $(CBENCHTEST)/bin
	ln -s $(CBENCHTEST)/$(SRC) $(CBENCHTEST)/bin
