include ../../make.def

CFLAGS = $(COMMON_FLAGS) -O1

EXEC = fpck
OBJS = fpck.o meminfo.o
INSTALLDIR = $(hwtest_bin_dir)
INSTALLTARGETS = $(EXEC)

default: shared

download:

shared: $(EXEC)

$(EXEC): $(OBJS)
	$(PLAINCC) -o $(EXEC) $(OBJS)

static: $(OBJS)
	$(PLAINCC) -static -o $(EXEC) $(OBJS)
	strip $(EXEC)

%.o: %.c
	$(PLAINCC) $(CFLAGS) -c $<

clean:
	rm -f $(EXEC) $(OBJS)

distclean: clean

install uninstall: default
	$(do-$@)
