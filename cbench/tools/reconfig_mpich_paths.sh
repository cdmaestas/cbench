#!/bin/bash

# arg1 is the ORIGINAL path where mpich was installed
# arg2 is the NEW path where mpich is installed
if [ -z $1 ]; then
	echo "USAGE: $0 /ORIG/path/to/mpich /NEW/path/to/mpich [path to fix files in]"
	exit 1
fi
if [ -z $2 ]; then
	echo "USAGE: $0 /ORIG/path/to/mpich /NEW/path/to/mpich [path to fix files in]"
	exit 1
fi


ORIG_DEST=$1
NEW_DEST=$2

if [ -z $3 ]; then
	# assume we are fixing the NEW destination
	cd ${NEW_DEST}
else
	cd $3
fi

for i in `grep -rl "${ORIG_DEST}" .`; do
	#echo sed -i "s:${ORIG_DEST}/::g" $i
	sed -i "s:${ORIG_DEST}:${NEW_DEST}:g" $i
done

#for i in `grep -rl "${WORKDIR}" etc`; do
#	sed -i "s:${WORKDIR}:${INSTALL_DEST}:g" $i
#done

#for wrapper in mpicc mpiCC mpicxx mpif77 mpif90; do
#  sed -i \
#	  -e "s/\(^BASE_LIB_LIST=.*\) \"/\1 -lsysfs\"/" \
#	  ${D}/${INSTALL_DEST}/bin/${wrapper}
#done

