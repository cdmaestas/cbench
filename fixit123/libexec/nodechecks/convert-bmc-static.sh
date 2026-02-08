#!/bin/bash 
#set -x
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

if [ -z $FIXIT123_HOME ]; then
	echo FIXIT123 environment variables not found!
	exit 1
fi

. $FIXIT123_HOME/libexec/nodechecks/dell_functions

NODE=`hostname`
IP=`grep ${NODE}-ipmi /etc/hosts | awk '{print $1}'`
SIP=""
LE=""
SOL=""
STATIC=""

# ipmi

is_omreport_found || exit 1
is_omconfig_found || exit 1

#
# omconfig always returns sucess, even if it didn't set a value
# hence, we have added loops and checks to verify things do get
# set correctly - EAE 10/19/2006
#

while [ "$LE" != "true" ]
do
	omconfig chassis bmc config=nic enable=true
    LE=`omreport chassis bmc config=nic | egrep -A1 \
        "Enable IPMI Over LAN$" | tail -1 | awk '{print $3}'`
done

while [ "$SOL" != "true" ]
do
	omconfig chassis bmc config=serialoverlan enable=true
    SOL=`omreport chassis bmc config=serialoverlan | egrep -A1 \
         "Enable Serial Over LAN$" | tail -1 | awk '{print $3}'`
done

while [ "$STATIC" != "Static" ]
do
	while [ "$IP" !=  "$SIP" ]
	do
		omconfig chassis bmc config=nic ipsource=static ipaddress=$IP \
             subnet=255.255.248.0
		SIP=`omreport chassis bmc config=nic | egrep -A 1 \
             "IP Address$" | tail -1 | awk '{print $3}'`
		STATIC=`omreport chassis bmc config=nic | egrep -A 1 \
             "IP Address Source" | tail -1 | awk '{print $3}'`
	done
done
