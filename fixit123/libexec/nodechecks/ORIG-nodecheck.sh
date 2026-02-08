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

export TERM=xterm

if [ $# -ne 0 ]; then
	if [ $1 = "fixit" ]; then
		FIXIT=1;
		FW_IMAGE=/home/dell/cisco/hca_fw/fw-lioncub-a0-test-4.7.0.bin
	fi
fi

KERNEL=2.6.9-15.EL.rootsmp
FW_VERSION=v4.7.0
FW_BUILD=3.2.0.39
BIOS_VERSION=A04
BMC_VERSION=1.40
BP_VERSION=1.00
BAUD_RATE=19200
#PANFS_VERSION=panfs-2.6.9-15.EL.root-mp-2.3.1-171331.15
PANFS_VERSION=panfs-2.6.9-15.EL.root-mp-2.3.2-175248.32

echo -n "Today's date is: "
date +%D

# source function library
. /etc/rc.d/init.d/functions

echo -n "Checking Kernel Version:"
if [ `uname -r` != $KERNEL ]; then
	echo_failure
else 
	echo_success
fi

echo
echo -n "Checking Processor Count:"
if [ `cat /proc/cpuinfo | grep processor | wc -l` -ne 2 ]; then
	echo_failure
else
	echo_success
fi

echo
echo "Checking for writeable areas in /var and /tmp"
echo -n "File touch test :"
touch /tmp/g /var/g /var/spool/g /var/spool/PBS/g
if [ $? -ne 0 ]; then
	echo_failure
	exit 1
else
	echo_success
fi

echo
echo -n "File removal test :"
rm -f /tmp/g /var/g /var/spool/g /var/spool/PBS/g
if [ $? -ne 0 ]; then
	echo_failure
	exit 1
else
	echo_success
fi

echo
echo -n "Checking for proper install location of Dell OMSA: "
if [ ! -d /var/dell/srvadmin ]; then
	echo_failure
	if [ $FIXIT ]; then
		echo
		echo "Attempting to upgrade Dell OMSA ... "
		/apps/breakfix-testing/SCRIPTS/dell-omsw-upgrade.sh
	fi
else
	echo_success
fi

echo
echo -n "Checking for installed firmware (BIOS BMC BP): "
if [ `omreport system version | grep -P '(BIOS|BMC|BP)' | wc -l` -lt 3 ]; then
	echo_failure
	exit 1
else

echo
echo -n "Checking BIOS Version ($BIOS_VERSION):"
if [ `omreport chassis bios | grep Version | awk '{print $3}'` != $BIOS_VERSION ]; then
	echo_failure
	if [ $FIXIT ]; then
		echo
		echo Attempting to update BIOS to $BIOS_VERSION ...
		/apps/breakfix-testing/SCRIPTS/update-firmware.sh bios
		echo Updated to BIOS $BIOS_VERSION, now rebooting ...
		echo Please re-run cap-nodecheck on this node when done ...
		umount /scratch3
		sleep 5
		reboot
		exit 1
	fi
else
	echo_success
fi

echo
echo -n "Checking BMC Version ($BMC_VERSION):"
if [ `omreport system version | grep -A 1 BMC | grep Version | awk '{print $3}'` != $BMC_VERSION ]; then
        echo_failure
        if [ $FIXIT ]; then
		echo
                echo Attempting to update BMC to $BMC_VERSION ...
		/apps/breakfix-testing/SCRIPTS/update-firmware.sh bmc
        fi
else
        echo_success
fi

echo
echo -n "Checking Primary BP Version ($BP_VERSION):"
if [ `omreport system version | grep -A 1 "Primary BP" | grep Version | awk '{print $3}'` = $BP_VERSION ]; then
	echo_success
else
	echo_failure
        if [ $FIXIT ]; then
		echo
                echo Attempting to update BP to $BP_VERSION ...
		/apps/breakfix-testing/SCRIPTS/update-firmware.sh bp
        fi
fi

echo
echo -n "Checking BMC for valid configuration"
if [ `omreport chassis bmc | grep -A1 -w "Attribute : IP Address Source" | grep Value | awk '{print $3}'` != "Static" ]; then
	echo_failure
        if [ $FIXIT ]; then
		echo
                echo Attempting to fix BMC IP configuration ...
		/apps/breakfix-testing/SCRIPTS/convert-bmc-static.sh
        fi
elif [ `omreport chassis bmc | grep -A1 -w "Attribute : IP Address$" | grep Value | awk '{print $3}'` = "0.0.0.0" ]; then
	echo_failure
        if [ $FIXIT ]; then
		echo
                echo Attempting to fix BMC IP configuration ...
		/apps/breakfix-testing/SCRIPTS/convert-bmc-static.sh
        fi
else
	echo_success
fi

fi

echo
echo -n "Checking for correct BIOS Baud Rate ($BAUD_RATE):"
if [ `omreport chassis biossetup | grep -A 1 BAUD | grep Setting | awk '{print $3}'` -ne $BAUD_RATE ]; then
	echo_failure
        if [ $FIXIT ]; then
		echo
		echo "Attempting BIOS setting fixes ..."
		/apps/breakfix-testing/SCRIPTS/dell/biosconf/cmoscfg -update -filename /apps/breakfix-testing/SCRIPTS/dell/biosconf/bios.dat 
		/apps/breakfix-testing/SCRIPTS/dell/omsa-bios.script 
		
	fi
else
	echo_success
fi

echo
echo -n "Checking for SCSI conversion:"
if [ `omreport chassis biossetup | grep -A1 "RAID On Motherboard" | grep Setting | awk '{print $3}'` != "SCSI" ]; then
	echo_failure
else
	echo_success
fi

echo
echo "Running Topspin ib checks:" 
echo "Checking Topspin ib status = FIRMWARE: `/usr/local/topspin/sbin/tvflash -i | grep Primary | awk '{print $4}' | cut -f1 -d','` BUILD: `/usr/local/topspin/sbin/tvflash -i | grep Primary | awk '{print $6}' | cut -f1 -d','`"
if [ -x /usr/local/topspin/sbin/tvflash ]; then
#	echo "Turning off and stop extra ts services (ts_srp and ts_customize)"
#	/sbin/chkconfig ts_srp off
#	/sbin/chkconfig ts_customize off
	echo -n "Checking Topspin ib firmware ($FW_VERSION build $FW_BUILD):"
	if [ `/usr/local/topspin/sbin/tvflash -i | grep Primary | awk '{print $4}' | cut -f1 -d','` = $FW_VERSION ]; then
		if [ `/usr/local/topspin/sbin/tvflash -i | grep Primary | awk '{print $6}' | cut -f1 -d','` = $FW_BUILD ]; then
		        echo_success
		else
			echo_failure
		        if [ $FIXIT ]; then
				echo
				echo Upgrading IB Firmware to $FW_VERSION ...
				/usr/local/topspin/sbin/tvflash $FW_IMAGE
        		fi
		fi
	else
		echo_failure
		if [ $FIXIT ]; then
			echo
			echo Upgrading IB Firmware to $FW_VERSION ...
			/usr/local/topspin/sbin/tvflash $FW_IMAGE
        	fi
	fi

	echo
	echo -n "Checking Topspin ib driver for clean NON-LA-MPI compliance:"
	if [ -f /usr/local/topspin/lib64/libvapi.so ]; then
		#if [ `strings /usr/local/topspin/lib64/libvapi.so | grep PREMAIN` = "NO_IB_PREMAIN_INIT" | wc -l` ]; then
		if [ `strings /usr/local/topspin/lib64/libvapi.so | grep PREMAIN | wc -l` -ne 0 ]; then
			echo_failure
			if [ $FIXIT ]; then
				echo
				echo Updating TopSpin RPMS ...
				/apps/breakfix-testing/SCRIPTS/ib-update.sh
	        	fi
	        else
			echo_success
		fi
	else
		echo_failure
	fi

	echo
	echo -n "Checking topspin ib status:" 
	if [ -d /usr/local/topspin ]; then
		if [ `/usr/local/topspin/bin/vstat | grep port_state=PORT_ACTIVE | wc -l` -ne 1 ]; then
			echo_failure
		else
			echo_success
		fi
	else 
		echo_failure
	fi
else
	echo
	echo -n "Topspin software may not be installed:"
        echo_failure
	if [ $FIXIT ]; then
		/apps/breakfix-testing/SCRIPTS/ib-update.sh
	fi
fi


echo
echo -n "Checking pbs_mom init state:"
if [ -x /etc/rc.d/init.d/pbs_mom ]; then

/sbin/chkconfig --list pbs_mom
if [ $? -ne 0 ]; then
	/sbin/chkconfig --add pbs_mom
	/sbin/chkconfig pbs_mom on
	echo -n "Fixed pbs_mom state:"
	echo_success
fi
if [ `/sbin/service pbs_mom status | awk '{print $3}'` = stopped ]; then
	/sbin/chkconfig pbs_mom on
	/sbin/service pbs_mom start
fi
else
	echo_failure
fi

echo
echo -n "Checking for proper number of NFS mounts:"
if [ `cat /proc/mounts | grep nfs1 | wc -l` -ne 3 ]; then
	echo_failure
else
	echo_success
fi

echo
echo -n "Checking for Panasas software:"
if [ `rpm -qa | grep panfs` = $PANFS_VERSION ]; then
	echo_success
else
	echo_failure
        if [ $FIXIT ]; then
		echo
                echo Attempting to update PANASAS to $PANFS_VERSION ...
		/apps/breakfix-testing/SCRIPTS/panfs-upgrade.sh
        fi
fi

echo
echo -n "Checking for proper Panasas mount:"
if [ `cat /proc/mounts | grep callback-address-ping | wc -l` -ne 1 ]; then
        echo_failure
	if [ $FIXIT ]; then
	        echo
		while [ `cat /proc/mounts | grep 205.137.90.1 | wc -l` -gt 0 ]
		do
			umount /scratch3 > /dev/null 2>&1
		done
		/apps/breakfix-testing/SCRIPTS/panfs-install.sh
	fi
else
	echo_success
fi
echo

#echo "Updating client ..."
#/apps/contrib/install/cap-updateclient.sh > /dev/null 2>&1
