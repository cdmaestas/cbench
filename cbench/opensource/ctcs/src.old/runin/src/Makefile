#
# Makefile for source packages inside Cerberus.
#

all: prandom chartst memtst flushb crashmex random;
#kconfig ltp smartsuite nbench

# smartsuite no longer a part of Cerberus.
#smartsuite: ;
#	sh -c 'if [ -z "$$VA_CERB_NOSMARTSUITE" ] ; then make -C ucsc-smartsuite; fi'

# nbench no longer a part of Cerberus
#nbench: ;
#	sh -c "make -C nbench-byte >>/dev/null 2>&1"

dist-clean: clean;
	rm -f ../bin/random
	rm -f ../bin/prandom
	# if flushb gets fixed, change this
	rm -f ../bin/flushb.real
#	rm -f ../bin/kconfig
	rm -f ../chartst
	rm -f ../memtst
	rm -f ../bin/smartctl
	sh -c "make -C cpuburn dist-clean"
	sh -c "make -C crashme dist-clean"
#	sh -c "make -C nbench-byte dist-clean"
#	sh -c "make -C ucsc-smartsuite dist-clean"

install: all ;
	cp random ../bin
	cp prandom ../bin
	cp flushb ../bin/flushb.real
#	cp kconfig ../bin
	cp chartst ..
	cp memtst.src/memtst ../memtst
#	sh -c 'if [ -z "$$VA_CERB_NOSMARTSUITE" ] ; then cp ucsc-smartsuite/smartctl ../bin ; fi'
	sh -c "make -C cpuburn install"
	sh -c "make -C crashme install >> /dev/null 2>&1"
#	sh -c "make -C nbench-byte >>/dev/null 2>&1"

memtst: ;
	make -C memtst.src

flushb: flushb.o ;
	$(CC) $(CFLAGS) -o flushb flushb.o -lm

random: random.o ;
	$(CC) $(CFLAGS) -o random random.o -lm

prandom: prandom.o ;
	$(CC) $(CFLAGS) -o prandom prandom.o -lm

chartst: chartst.o ;
	$(CC) $(CFLAGS) -o chartst chartst.o -lm

#kconfig: kconfig.o ;
#	$(CC) $(CFLAGS) -o kconfig kconfig.o -lm

crashmex: ;
	make -C crashme >>/dev/null 2>&1

# ltp removed from cerberus
#ltpx: ;
#	make -C ltp

clean: ;
	rm -f *.o prandom chartst flushb random
	# kconfig
	make -C memtst.src clean
	make -C cpuburn clean
	make -C crashme clean
#	make -C ucsc-smartsuite clean
#	make -C ltp clean
