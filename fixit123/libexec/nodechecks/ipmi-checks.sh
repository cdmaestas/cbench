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

if [ -z $1 ]; then
	echo $0 hostname
	exit;
fi

IP=`grep ${1}-ipmi /etc/hosts | awk '{print $1}'`
if [ -z $IP ]; then
	echo "$0: $1 is an invalid host name!"
	exit;
fi

# source function library
. /etc/rc.d/init.d/functions

echo "--- $1 System Power Information ---"
ipmish -ip $IP -u root -p calvin power status
echo "--- $1 isol baud rate config ---"
ipmitool -H $IP -U root -P calvin isol setup 19200
echo "--- $1 service TAG ---"
ipmish -ip $IP -u root -p calvin sysinfo fru | grep ^Servicetag=
echo "--- $1 System Event Log ---"
ipmish -ip $IP -u root -p calvin sel get
echo "--- $1 System Information ID ---"
ipmish -ip $IP -u root -p calvin sysinfo id
echo "--- $1 System Information FRU ---"
ipmish -ip $IP -u root -p calvin sysinfo fru
#echo "--- $1 System Information SDR ---"
#ipmitool -H $IP -U root -P calvin sdr
echo "--- $1 System Chassis Status ---"
ipmitool -H $IP -U root -P calvin chassis status
