all: crashme 
#pddet

install: all
	cp crashme ../../bin
clean:
	rm -f crashme.o crashme

dist-clean: clean
	rm -f ../../bin/crashme

crashme:	crashme.o
	$(CC) $(CFLAGS) -o crashme crashme.o
# TODO: fix all the warnings.
crashme.o: crashme.c
	$(CC) $(CFLAGS) -c crashme.c

#pddet:	pddet.o
#	gcc -O6 -o pddet pddet.o
#pddet.o: pddet.c
#	gcc -O6 -c pddet.c

