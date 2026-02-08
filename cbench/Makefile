# vim: syntax=make tabstop=4
###############################################################################
#    Copyright (2005) Sandia Corporation.  Under the terms of Contract
#    DE-AC04-94AL85000 with Sandia Corporation, the U.S. Government retains
#    certain rights in this software
#
#    This file is part of Cbench.
#
#    Cbench is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    any later version.
#
#    Cbench is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Cbench; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
###############################################################################

include make.def

HW_TESTS = fpck ctcs memtester streams nodeperf llcbench stress matmult stride stab lmbench streams-benchmarks

STANDALONEOPEN_TESTS = b_eff mpi_latency mpi_hello mpi_hello_ordered mpi_overhead \
             mpi_routecheck rotate IMB osutests stab perftest mpi_examples mpi_slowcpu \
             osu-micro-benchmarks intel-mpi-benchmarks\
             mpi_malloc mpi_tokensmash phloem simul graph500 \
             hdparm dt iozone bonnie++ ior_bench miranda_io \
             fdtree mdtest lanl \
             HPLlinpack hpcc HPLinpack2 NPB 

OPEN_TESTS = b_eff mpi_latency mpi_hello mpi_hello_ordered mpi_overhead \
             mpi_routecheck ior_bench iozone bonnie++ rotate HPLlinpack \
             IMB osutests lanl stab perftest mpi_examples mpi_slowcpu \
             mpi_malloc mpi_tokensmash phloem HPLinpack2 \
             fdtree simul mdtest miranda_io graph500 hwloc

OPEN_APP_TESTS = amg hpccg irs phdmesh sppm sweep3d trilinos

OPENEXTRAS_TESTS = NPB hpcc

GPU_TESTS = shoc HPLinpack-gpu

# all of these live in the opensource/ area
HWTEST_SUBDIRS     = $(addprefix opensource/, $(HW_TESTS))
OPEN_SUBDIRS       = $(addprefix opensource/, $(OPEN_TESTS))
OPENEXTRAS_SUBDIRS = $(addprefix opensource/, $(OPENEXTRAS_TESTS))
GPU_SUBDIRS	   = $(addprefix opensource/, $(GPU_TESTS))
STANDALONEOPEN_SUBDIRS       = $(addprefix opensource/, $(STANDALONEOPEN_TESTS))

SUBDIRS = $(OPEN_SUBDIRS) $(HWTEST_SUBDIRS) $(GPU_SUBDIRS)

ifndef BINIDENT
  BINDIR = bin
else
  BINDIR = bin.$(BINIDENT)
endif
  DEST = $(BENCH_TEST)/$(BINDIR)

# by default build all the standard opensource set of binaries
default: open hwtest

open: $(OPEN_SUBDIRS)
	$(do-open-subdirs)

extras: $(OPENEXTRAS_SUBDIRS)
	$(do-openextras-subdirs)

iotest:
	$(MAKE) -C opensource/iozone
	$(MAKE) -C opensource/ior_bench
	$(MAKE) -C opensource/iozone install
	$(MAKE) -C opensource/ior_bench install

hwtest: $(HWTEST_SUBDIRS)
	$(do-hwtest-subdirs) 
	$(MAKE) -C opensource/iozone
	$(MAKE) -C opensource/iozone install

# target used to build only the binaries needed to fully utilize the 
# NODEHWTEST testset, i.e. compile only what is needed for node-level testing
nodehwtest: hwtest standalone standaloneinstall
	$(MAKE) -C opensource/NPB serial
	$(call do-hwtest-subdirs,install)

#
# BEGIN OPENAPPS
#
openapps_download:
	for OAPP in $(OPEN_APP_TESTS); do \
		[ -d openapps/$$OAPP ] && $(MAKE) -C openapps/$$OAPP download; \
	done;
openapps_compile: openapps_download
	for OAPP in $(OPEN_APP_TESTS); do \
		[ -d openapps/$$OAPP ] && $(MAKE) -C openapps/$$OAPP; \
	done;
openapps_install: openapps_compile
	for OAPP in $(OPEN_APP_TESTS); do \
		[ -d openapps/$$OAPP ] && $(MAKE) -C openapps/$$OAPP install; \
	done;
#
# END OPENAPPS
#

#
# BEGIN STANDALONE 
#
cbench_standalone_sysprogs_distclean:
	$(call print-header,"cbench standalone sysprogs distclean")
	$(call print-header,"cbench standalone sysprogs pdsh distclean")
	$(MAKE) -C opensource/pdsh distclean
	$(call print-header,"cbench standalone sysprogs ompi distclean")
	$(MAKE) -C opensource/ompi distclean
	$(call print-header,"cbench standalone sysprogs OpenBLAS distclean")
	$(MAKE) -C opensource/OpenBLAS distclean
cbench_standalone_sysprogs_clean:
	$(call print-header,"cbench standalone sysprogs clean")
	$(call print-header,"cbench standalone sysprogs pdsh clean")
	$(MAKE) -C opensource/pdsh clean
	$(call print-header,"cbench standalone sysprogs ompi clean")
	$(MAKE) -C opensource/ompi clean
	$(call print-header,"cbench standalone sysprogs OpenBLAS clean")
	$(MAKE) -C opensource/OpenBLAS clean
cbench_standalone_sysprogs_download:
	$(call print-header,"cbench standalone sysprogs download")
	$(call print-header,"cbench standalone sysprogs pdsh download")
	$(MAKE) -C opensource/pdsh download
	$(call print-header,"cbench standalone sysprogs ompi download")
	$(MAKE) -C opensource/ompi download
	$(call print-header,"cbench standalone sysprogs OpenBLAS download")
	$(MAKE) -C opensource/OpenBLAS download
cbench_standalone_sysprogs_compile:
	$(call print-header,"cbench standalone sysprogs compile")
	$(call print-header,"cbench standalone sysprogs pdsh compile")
	$(MAKE) -C opensource/pdsh 
	$(call print-header,"cbench standalone sysprogs ompi compile")
	$(MAKE) -C opensource/ompi 
	$(call print-header,"cbench standalone sysprogs OpenBLAS compile")
	$(MAKE) -C opensource/OpenBLAS 
cbench_standalone_sysprogs_install:
	$(call print-header,"cbench standalone sysprogs install")
	@sbin/install_cbenchtest --testtop
	$(call print-header,"cbench standalone sysprogs pdsh install")
	$(MAKE) -C opensource/pdsh install
	$(call print-header,"cbench standalone sysprogs ompi install")
	$(MAKE) -C opensource/ompi install
	$(call print-header,"cbench standalone sysprogs OpenBLAS install")
	$(MAKE) -C opensource/OpenBLAS install
cbench_standalone_sysprogs_reinstall:
	$(call print-header,"cbench standalone sysprogs reinstall")
	@sbin/install_cbenchtest --testtop
	$(call print-header,"cbench standalone sysprogs pdsh reinstall")
	$(MAKE) -C opensource/pdsh reinstall
	$(call print-header,"cbench standalone sysprogs ompi reinstall")
	$(MAKE) -C opensource/ompi reinstall
	$(call print-header,"cbench standalone sysprogs OpenBLAS reinstall")
	$(MAKE) -C opensource/OpenBLAS reinstall

cbench_standalone_hwtestdirs_distclean: 
	$(call print-header,"cbench standalone hwtestdirs distclean")
	$(call do-hwtest-subdirs,distclean)
cbench_standalone_hwtestdirs_clean:
	$(call print-header,"cbench standalone hwtestdirs clean")
	$(call do-hwtest-subdirs,clean)
cbench_standalone_hwtestdirs_download:
	$(call print-header,"cbench standalone hwtestdirs download")
	$(call do-hwtest-subdirs,download)
cbench_standalone_hwtestdirs_compile: cbench_standalone_sysprogs_install
	$(call print-header,"cbench standalone hwtestdirs compile")
	$(do-hwtest-subdirs)
cbench_standalone_hwtestdirs_install: cbench_standalone_sysprogs_install
	$(call print-header,"cbench standalone hwtestdirs install")
	$(call do-hwtest-subdirs,install)

cbench_standalonedir_alldistclean: cbench_standalone_sysprogs_distclean cbench_standalone_hwtestdirs_distclean
	$(call print-header,"cbench standalone alldistclean")
	$(call do-standaloneopen-subdirs,distclean)
	$(call print-header,"cbench standalone HPLintel alldistclean")
	$(MAKE) -C opensource/HPLintel distclean
cbench_standalonedir_distclean: cbench_standalone_hwtestdirs_distclean
	$(call print-header,"cbench standalone distclean")
	$(call do-standaloneopen-subdirs,distclean)
	$(call print-header,"cbench standalone HPLintel distclean")
	$(MAKE) -C opensource/HPLintel distclean
cbench_standalonedir_clean: cbench_standalone_hwtestdirs_clean
	$(call print-header,"cbench standalone clean")
	$(call do-standaloneopen-subdirs,clean)
	$(call print-header,"cbench standalone HPLintel clean")
	$(MAKE) -C opensource/HPLintel clean
cbench_standalonedir_download: cbench_standalone_sysprogs_download cbench_standalone_hwtestdirs_download
	$(call print-header,"cbench standalonedir download")
	$(call do-standaloneopen-subdirs,download)
cbench_standalonedir_compile: cbench_standalone_sysprogs_install cbench_standalone_hwtestdirs_compile
	$(call print-header,"cbench standalonedir compile")
	$(do-standaloneopen-subdirs)
cbench_standalonedir_install: cbench_standalone_sysprogs_install cbench_standalone_hwtestdirs_install
	$(call print-header,"cbench standalonedir install")
	$(call do-standaloneopen-subdirs,install)
	$(do-compiled-bin-installs-binident)
	@sbin/install_cbenchtest --allsets --bindir $(BINDIR)

cbench_standalone: cbench_standalonedir_download cbench_standalonedir_install
cbench_standalone_nonet: cbench_standalonedir_clean cbench_standalonedir_install

#
# END STANDALONE 
#

# targets to compile the Cbench standalone MPI
mpich: opensource/mpich/lib/libmpich.a
opensource/mpich/lib/libmpich.a:
	$(MAKE) -C opensource/mpich clean
	$(MAKE) -C opensource/mpich

# compile the standalone MPI binaries used in the NODEHWTEST testset
standalone: mpich
	$(MAKE) CBENCH_STANDALONE=yes -C opensource/lanl clean
	$(MAKE) CBENCH_STANDALONE=yes -C opensource/lanl
	$(MAKE) CBENCH_STANDALONE=yes -C opensource/HPLlinpack clean
	$(MAKE) CBENCH_STANDALONE=yes -C opensource/HPLlinpack
	$(MAKE) CBENCH_STANDALONE=yes -C opensource/HPLinpack2 clean
	$(MAKE) CBENCH_STANDALONE=yes -C opensource/HPLinpack2
	$(MAKE) CBENCH_STANDALONE=yes -C opensource/hpcc clean
	$(MAKE) CBENCH_STANDALONE=yes -C opensource/hpcc
# install the standalone MPI binaries used in the NODEHWTEST testset
standaloneinstall:
	$(MAKE) -C opensource/mpich install
	$(MAKE) CBENCH_STANDALONE=yes -C opensource/lanl install
	$(MAKE) CBENCH_STANDALONE=yes -C opensource/HPLlinpack install
	$(MAKE) CBENCH_STANDALONE=yes -C opensource/HPLinpack2 install
	$(MAKE) CBENCH_STANDALONE=yes -C opensource/hpcc install

# compile and install HPCC
hpcc:
	$(MAKE) -C opensource/hpcc normal
	$(MAKE) -C opensource/hpcc install

# compile and install GPU Tests
gpu: $(GPU_SUBDIRS)
	$(do-gputests-subdirs) 

# install all the default compiled binaries
install uninstall: default
	$(do-subdirs)

# install the Cbench testing tree (CBENCHTEST variable must be set)
installtests itests:
	@sbin/install_cbenchtest --testtop
	$(do-compiled-bin-installs-binident)
	@sbin/install_cbenchtest --allsets --bindir $(BINDIR)

# just install compiled binaries in to the Cbench testing tree
installcbenchbins: install
	@sbin/install_cbenchtest --testtop
	$(do-compiled-bin-installs-binident)

# update the core parts of the Cbench testing tree
update: 
	@sbin/install_cbenchtest --testtop

download:
	$(do-subdirs)

# compile and install LAMMPS
lammps: install 
	$(do-lammps-install)
	@sbin/install_cbenchtest --testset lammps

#cbench-tests-rpm: 

clean:
	$(do-subdirs)
	$(MAKE) -C opensource/hpcc clean
	rm -rf bin VERSION.snapshot cbench_snapshot_*.tar.gz cbench_release_*.tar.gz

distclean: clean
	$(MAKE) -C opensource/hpcc distclean
	$(MAKE) -C opensource/NPB distclean
	$(MAKE) -C opensource/mpich distclean
	$(MAKE) -C opensource/shoc distclean
	$(do-subdirs)

# targets used for making tarballs
sfrelease: 
	@echo "Updating from svn tree" && svn up; \
	if [ `svn stat $(CBENCHOME) | wc -l` -ne 0 ]; then echo "svn tree is not clean to make a release" && svn stat $(CBENCHOME) && exit 1; fi; 
	@export cbench_rev=`grep Version VERSION | awk -F ': ' '{print $$2}'`; \
	rm -fr /tmp/cbench_$${cbench_rev} /tmp/cbench_release_$${cbench_rev}\.tar.gz; \
	mkdir -p /tmp/cbench_$${cbench_rev}; tar cfz /tmp/cbench_release_$${cbench_rev}\.tar.gz * --exclude .svn --exclude restricted --exclude openapps; \
	cd /tmp/cbench_$${cbench_rev}; tar -zxf /tmp/cbench_release_$${cbench_rev}\.tar.gz; \
	cd /tmp && rm -f /tmp/cbench_release_$${cbench_rev}\.tar.gz && tar -zcf /tmp/cbench_release_$${cbench_rev}\.tar.gz cbench_$${cbench_rev}; \
	cd $(CBENCHOME) && rm -fr /tmp/cbench_$${cbench_rev} && echo "CBENCH RELEASE is /tmp/cbench_release_$${cbench_rev}.tar.gz";

release: distclean
	export cbench_rev=`grep Version VERSION | awk -F ': ' '{print $$2}'`; tar cfvz cbench_release_$${cbench_rev}\.tar.gz * --exclude cbench*.tar.gz --exclude CVS --exclude .svn --exclude restricted --exclude *.o --exclude bin --exclude openapps

repo_release: distclean
	export cbench_rev=`grep Version VERSION | awk -F ': ' '{print $$2}'`; export cbench_tag=`svn info . | grep Revision | awk '{print $$2}'`; tar cfvz cbench_snapshot_$${cbench_rev}-$${cbench_tag}\.tar.gz * --exclude cbench*.tar.gz --exclude CVS --exclude .svn --exclude restricted --exclude *.o --exclude bin --exclude openapps

apps_release: distclean
	export cbench_rev=`grep Version VERSION | awk -F ': ' '{print $$2}'`; tar cfvz cbench_app_release_$$cbench_rev\.tar.gz * --exclude cbench*.tar.gz --exclude CVS --exclude .svn --exclude restricted --exclude *.o --exclude bin 

restricted_release: distclean
	export cbench_rev=`grep Version VERSION | awk -F ': ' '{print $$2}'`; tar cfvz cbench_restricted_release_$$cbench_rev\.tar.gz * --exclude cbench*.tar.gz --exclude CVS --exclude .svn --exclude *.o --exclude bin 

#
# backdoor shorcuts for developers...
#

# compile most everything in the main tree except nodehwtest stuff
domostall: 
	$(MAKE) distclean
	$(MAKE) install
	$(MAKE) hpcc

# compile everything in the main tree (not openapps for example)!
doitall: 
	$(MAKE) distclean
	$(MAKE) install
	$(MAKE) hpcc
	$(MAKE) nodehwtest
	$(MAKE) gpu
