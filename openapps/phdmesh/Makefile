include $(CBENCHOME)/make.def

export CFLAGS

SRC=phdMesh
TAR=$(SRC).tar.gz
URL=https://software.sandia.gov/mantevo/downloads/$(TAR)

EXECS = $(SRC)/build_cbench/test_mesh.exe $(SRC)/build_cbench/test_mesh_big.exe
INSTALLDIR = $(bin_dir)
INSTALLTARGETS = $(EXECS)

PHDMESH_PATH := $(shell pwd)/src
export PHDMESH_PATH 

all normal: $(SRC)
	cd $(SRC)/build_cbench &&  CC=$(CC) CXX=$(CXX) LDCXX=$(CXX) ./build.cbench all
#	$(MAKE) CXX=$(CXX) LDCXX=$(CXX) PHDMESH_PATH=$(PHDMESH_PATH) -C $(SRC)/build_cbench -f ../Make.in all
#	$(MAKE) CXX=$(CXX) LDCXX=$(CXX) PHDMESH_PATH=$(PHDMESH_PATH) CFLAGS_INC="-I$(PHDMESH_PATH) -I$(PHDMESH_PATH)/include" -C $(SRC)/build_cbench -f ../Make.in all

$(SRC): $(TAR)
	-[ ! -d $(SRC) ] && mkdir $(SRC)
	cd $(SRC); tar zxf ../$(TAR)
	/bin/ln -sf $(SRC) src
	-[ ! -d $(SRC)/build_cbench ] && mkdir $(SRC)/build_cbench
	cd $(SRC)/build_cbench && /bin/ln -sf ../../build.cbench build.cbench
	patch -p0 < test_mesh_big.patch

$(TAR) download:
	$(call download-wget-url,$(URL))
	-[ -e $(TAR) ] && touch $(TAR)

clean:
	[ -d $(SRC) ] && cd $(SRC)/build_cbench &&  CC=$(CC) CXX=$(CXX) LDCXX=$(CXX) ./build.cbench clean

distclean:
	/bin/rm -rf $(SRC) $(TAR) src

install uninstall:
	$(do-$@)

include $(CBENCHOME)/make.inc
