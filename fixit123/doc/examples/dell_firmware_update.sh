#!/bin/bash
#set -ex

. /projects/contrib/fixit/fixit-env.sh

if [ -z $NODECHECKS_HOME ]; then
	echo Please define NODECHECKS_HOME env variable
	exit 1
fi
. $NODECHECKS_HOME/os_functions
. $NODECHECKS_HOME/dell_functions
if [ -f /etc/sysconfig/cap ]; then
	. /etc/sysconfig/cap
else
	echo Please define the role of this node
	exit 1
fi

omsa_check_src_dir /usr/src/dell
echo
if [ $? -eq 0 ]; then
    DELL_OMSA_SRC_OK=1
    /usr/src/dell/linux/supportscripts/srvadmin-services.sh start > /dev/null 2>&1
	service ipmi stop
else
    DELL_OMSA_SRC_OK=0
fi


#
# setup dtk stuff
#
export PATH=/projects/global/noarch/dell/dtk2.2/toolkit/bin:$PATH
export LD_LIBRARY_PATH=/projects/global/noarch/dell/dtk2.2/toolkit/bin:$LD_LIBRARY_PATH
# turn off memory checks in bios
syscfg --memtest=disable



WANT_REBOOT=0;

omsa_check_bmc_version 1.52
if [ $? -ne 0 ]; then
	omsa_update_firmware bmc 1.52
	WANT_REBOOT=0
fi

omsa_check_bp_version 1.00
if [ $? -ne 0 ]; then
    omsa_update_firmware bp 1.00
	WANT_REBOOT=0
fi

omsa_check_for_bmc_static_ip
if [ $? -ne 0 ]; then
	omsa_update_bmc_to_static_ip
fi

omsa_check_bios_baud_rate 19200
if [ $? -ne 0 ]; then
	omsa_update_bios_baud_rate
fi

if [ $CAPROLE = "worker" ]; then
	# check if on srn
	/sbin/ifconfig | grep 134.253 > /dev/null 2>&1
	if [ $? -ne 0 ]; then
		omsa_check_for_scsi_conversion
	fi

fi

omsa_check_bios_version A05
if [ $? -ne 0 ]; then
	omsa_update_firmware bios A05
	exit 1
fi
echo
#if [ $WANT_REBOOT -eq 1 ]; then
#	echo "This node needs a reboot"
#fi

if [ $DELL_OMSA_SRC_OK -eq 1 ]; then
    /usr/src/dell/linux/supportscripts/srvadmin-services.sh stop > /dev/null 2>&1
fi

