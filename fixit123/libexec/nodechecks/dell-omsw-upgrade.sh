#!/bin/bash
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

. /root/cluster-env.cfg
DELLOMSW_PREFIX=/var/dell/srvadmin
DELLOMSW_SRC=OMI-SrvAdmin-Dell-Web-LX-450-32-335_A00.tar.gz
DELLOMSW_DIR=${CONTRIBDIR}/SOURCES
export DELLOMSW_SRC DELLOMSW_DIR DELLOMSW_PREFIX

#
# requires up2date to be configured correctly
# requires compat-libstdc++, netsnmp
#
#up2date --nox -i netsnmp compat-libstdc++ kernel-source >> ${KS_LOGFILE} 2>&1
echo "Updating needed software dependencies if any ..."
up2date --nox -i netsnmp >> ${KS_LOGFILE} 2>&1
up2date --nox -i -f kernel-devel >> ${KS_LOGFILE} 2>&1

if [ ! -f /usr/src/dell/linux/supportscripts/srvadmin-uninstall.sh ]; then
	echo "Dell OMSA Package Upgrade: ERROR: NON-EXISTENT UNINSTALL SCRIPT!"
	exit 1
else
	/usr/src/dell/linux/supportscripts/srvadmin-uninstall.sh -f
fi

mkdir -p /usr/src/dell
cd /usr/src/dell
rm -fr linux
wget http://${HTTP_SERVER}/${DELLOMSW_DIR}/${DELLOMSW_SRC}
tar -zxf ${DELLOMSW_SRC}
rm -f ${DELLOMSW_SRC}
if [ ! -d /usr/src/dell/linux/supportscripts ]; then
	echo "Kikcstart Install: Dell OMSA Package: ERROR: DELL OMSW PACKAGE DIR STRUCTURE HAS CHANGED!" 
	exit 1
fi

if [ $DELLOMSW_PREFIX != "/opt/dell" ]; then
	/usr/bin/perl -spi -e 's|INSTALL_PREFIX=""$|INSTALL_PREFIX="$ENV{DELLOMSW_PREFIX}"|' /usr/src/dell/linux/supportscripts/srvadmin-install.sh
fi

#
# need to fool it that we are installing in an xterminal environment - cdm
#
TERM=xterm
export TERM
/usr/src/dell/linux/supportscripts/srvadmin-install.sh -b -d 
/usr/src/dell/linux/supportscripts/srvadmin-services.sh start 
