include ../../make.def

VERSION=1.0.4
SRC=stress-$(VERSION)
TAR=$(SRC).tar.gz
#URL="http://weather.ou.edu/~apw/projects/stress/$(TAR)"
# new location
URL="http://people.seas.harvard.edu/~apw/stress/$(TAR)"
# backup location for git
#TAR=$(SRC).git
#URL=https://github.com/cooljeanius/$(SRC)

EXEC=src/src/stress
INSTALLDIR = $(hwtest_bin_dir)
INSTALLTARGETS = $(EXEC)

default: $(EXEC)

download: $(TAR)

$(TAR):
	$(call download-curl-url,$(URL))
#	$(call gitpull-src,$(URL), $(TAR))

$(SRC): $(TAR)
	$(call untar-src,$(TAR))
	ln -sf $@ src
	@[ -d $@ ] && touch $@

.configure-$(SRC): $(SRC) 
	@echo "Configuring: $(SRC)"
	cd src && ./configure > ../.configure-$(SRC) 2>&1
	@touch $@

$(EXEC) .make-$(SRC): .configure-$(SRC)
	@echo "Compiling: $(SRC)"
	$(MAKE) -C src > .make-$(SRC) 2>&1
	@touch $@

clean: 
	-$(MAKE) -C src clean > .make-$(SRC) 2>&1
	rm -f .make-$(SRC)

distclean:
	/bin/rm -rf $(SRC) $(TAR) src .make-$(SRC) .configure-$(SRC)

install uninstall: default
	$(do-$@)
