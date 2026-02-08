#
# Makefile for the Cerberus Runin Authoring Program.
#

# Debug
#CC=cc
#CFLAGS=-Wall -g

include HostVars.mk

# Production
#export CC=egcs
ifeq ($(MACHINE),ppc)
	export CC?=gcc
	export CFLAGS?=-Wall -O6 -finline-functions -funroll-loops
else
ifeq ($(MACHINE),sparc)
	export CC?=gcc
	export CFLAGS?=-Wall -O2 -fomit-frame-pointer -finline-functions -funroll-loops
else
ifeq ($(MACHINE),sparc64)
	export CC?=gcc
	export CFLAGS?=-Wall -O2 -mv8 -mtune=ultrasparc -fomit-frame-pointer -finline-functions -funroll-loops
else
ifeq ($(MACHINE),x86_64)
	export CC?=gcc
	export CFLAGS?=-Wall -O6 -finline-functions -funroll-loops -m64
else
ifeq ($(MACHINE),ia64)
	export CC?=gcc
	export CFLAGS?=-Wall -O6 -finline-functions -funroll-loops
else
	export CC?=gcc
	export CFLAGS?=-Wall -O6 -mcpu=pentiumpro -finline-functions -funroll-loops 
endif
endif
endif
endif
endif
#-D__NEW_HD_DRIVE_ID

all: symlinks;
	make -C runin all
	make -C runin install

HostVars.mk:
	sh -c "echo # this file is dynamically generated > HostVars.mk"
	sh -c "echo export MACHINE=`uname -m` >> HostVars.mk"

symlinks:
	make -C runin symlinks 

spec: ctcs.spec ;


ctcs.spec:
	./genspec

requirements: ;
	./check-requirements

test: symlinks ;
	./check-syntax
	make dist-clean

install: all ;

clean: ;
	make -C runin clean
	rm -f `find -name "core" -print`
	rm -f HostVars.mk
	
src-dist-clean: ;
	make -C runin dist-clean

dist-clean: src-dist-clean clean ;
	rm -rf .*.tcf.log.*  .newburn.old.* newburn.tcf newburn2.tcf newburn.params newburn2.params
	rm -f `find -name "*~" -print`
	rm -f `find -name "#*#" -print`
cvs-clean:
	 rm -rf `find . -name CVS`
