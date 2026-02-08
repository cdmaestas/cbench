include ../../make.def

MPICH_VERSION = 1.2.6
MPICH = mpich-$(MPICH_VERSION)
CH=ch_shmem

default: .make-$(MPICH)

.make-$(MPICH): .configure-$(MPICH)
	(cd $(MPICH); make && make install)
	touch $@

.configure-$(MPICH): $(MPICH)
	(cd $(MPICH); export CC=$(PLAINCC); export F77=$(PLAINF77); \
	 export FC=$(PLAINF77); export CXX=$(PLAINCXX); \
	 export CFLAGS='-O1'; export LDFLAGS='-lpthread'; \
	 ./configure --enable-f77 --with-device=$(CH) --without-romio \
	 --enable-cxx --enable-shared --prefix=$(BENCH_HOME)/opensource/mpich)
	@touch $@

# target to untar the mpich distribution
$(MPICH):
	@echo getting source for $(MPICH) ...
	@if [ -f $(MPICH).tar.gz ] ; then				\
		zcat $(MPICH).tar.gz | tar xf -;			\
	elif [ -f $(MPICH).tar.bz2 ] ; then 			\
		bzcat $(MPICH).tar.bz2 | tar xf -;			\
	elif [ -f $(MPICH).tar ] ; then 				\
		cat $(MPICH).tar | tar xf -;			\
	else								\
		echo No $(MPICH) found;				\
		exit 1;							\
	fi
	for p in `ls ../patch* | grep $(MPICH_VERSION)` ; do	\
		patch -N -p1 < $$p ;	\
	done;

install:
	cd $(MPICH) && make PREFIX=$(CBENCHTEST)/mpich install
	rm -rf $(CBENCHTEST)/mpich/doc $(CBENCHTEST)/mpich/share $(CBENCHTEST)/mpich/etc $(CBENCHTEST)/mpich/examples $(CBENCHTEST)/mpich/man $(CBENCHTEST)/mpich/www

clean:
	-$(MAKE) -C $(MPICH) distclean
	rm -f .make-$(MPICH) .configure-$(MPICH)
	rm -rf bin etc include sbin www doc examples lib man share logfiles

distclean: clean
	rm -rf $(MPICH)
