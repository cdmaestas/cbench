#
# Makefile for the cpuburn program, by Jason T. Collins
# .S from Robert Redelmeier's makefile added for 1.4
#

all: zall ;

ifeq ($(MACHINE),ppc)
zall:
else
ifeq ($(MACHINE),sparc)
zall:
else
ifeq ($(MACHINE),sparc64)
zall:
else
ifeq ($(MACHINE),ia64)
zall:
else
zall: burnP6 burnMMX burnK6 burnP5 burnBX burnK7; 
endif
endif
endif
endif

dist-clean:
	rm -f ../../bin/burnP6
	rm -f ../../bin/burnMMX
	rm -f ../../bin/burnK6
	rm -f ../../bin/burnP5
	rm -f ../../bin/burnBX
	rm -f ../../bin/burnK7

ifeq ($(MACHINE),ppc)
install: all ;
else
ifeq ($(MACHINE),sparc64)
install: all ;
else
ifeq ($(MACHINE),sparc)
install: all ;
else
install: all ;
	cp burnP6 ../../bin
	cp burnMMX ../../bin
	cp burnK6 ../../bin
	cp burnP5 ../../bin
	cp burnBX ../../bin
	cp burnK7 ../../bin
endif
endif
endif

clean: ;
	rm -f *.o burnK6 burnP5 burnMMX burnP6 burnBX burnK7

.S:
	gcc -m32 -s -nostdlib -o $@ $<
