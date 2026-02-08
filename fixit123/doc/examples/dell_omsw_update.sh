#!/bin/bash
#set -ex

. /projects/contrib/fixit/fixit-env.sh

echo -n "Today's date is: "
date +%D

if [ -z $NODECHECKS_HOME ]; then
	echo Please define NODECHECKS_HOME env variable
	exit 1
fi

. $NODECHECKS_HOME/dell_functions

CONTRIBDIR=/linux/contrib
#DELLOMSW_SRC=OMI-SrvAdmin-Dell-Web-LX-450-32-335_A00.tar.gz
#DELLOMSW_SRC=OMI-50-MN-LX_A01.tar.gz
DELLOMSW_SRC=OM_5.1_ManNode_LIN_A00.tar.gz
DELLOMSW_DIR=${CONTRIBDIR}/SOURCES

# Dell checks
rpm -qa | grep srvadmin | grep 5.1 > /dev/null  2>&1
if [ $? -ne 0 ]; then
	# arg1 = http server, arg2 = http dir, 
	# arg3 = install dir, arg4 = omsa_src_pkg_name
	omsa_update $CAPBOSS ${DELLOMSW_DIR} /var/local ${DELLOMSW_SRC}
fi

if [ -d /var/dell ]; then
	# arg1 = http server, arg2 = http dir, 
	# arg3 = install dir, arg4 = omsa_src_pkg_name
	omsa_update $CAPBOSS ${DELLOMSW_DIR} /var/local ${DELLOMSW_SRC}
	rm -fr /var/dell
fi

omsa_check_install_dir /var/local 
if [ $? -ne 0 ]; then
	# arg1 = http server, arg2 = http dir, 
	# arg3 = install dir, arg4 = omsa_src_pkg_name
	omsa_update $CAPBOSS ${DELLOMSW_DIR} /var/local ${DELLOMSW_SRC}
fi
echo
