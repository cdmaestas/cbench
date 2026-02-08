include ../../make.def

#mpirun -np N ./fs_test.x -target /path/to/out.%s.%r -io mpi -barriers aopen -shift -nodb -type 1 -sync -size 1048576 -time 300
#where N is the number of ranks to run, and /path/to is the lustre mount.  We would be looking at "Effective Elapsed Bandwidth" for both write and read.

SRC=fs_test
TAR=$(SRC).git
URL="https://github.com/fs-test/$(TAR)"

default: .make-$(SRC)

download: $(TAR)

$(TAR):
	$(call gitpull-src,$(URL),$(TAR))

$(SRC): $(TAR)
	ln -sf $(TAR) src
	@[ -d $@ ] && touch $@

.make-$(SRC): $(SRC)
	make -C src/$(SRC) > .make-$(SRC) 2>&1
	@touch $@

clean:

distclean:
	rm -fr .make-$(SRC) src $(TAR) $(SRC) .install-$(SRC)

install:
