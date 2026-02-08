#!/bin/bash
# vim: syntax=sh tabstop=4
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

# set -x

# check for what profile script gives us
if [ -z $FIXIT123_HOME ]; then
    echo "FAILURE  FIXIT123_HOME variable not defined!"
    exit 1
fi

LOGDIR=$FIXIT123_DB_HOME
MAINLOG=$LOGDIR/breakfix.log
STEP3LOG=$LOGDIR/breakfix_step3.log
BINDIR=$FIXIT123_HOME/bin
TMPFILE="/tmp/step2a.tmp.$$"
HWTDIR=$FIXIT123_CBENCHTEST/nodehwtest

# source common step123 stuff
. $FIXIT123_HOME/libexec/common_step123


mkdir -p $LOGDIR
mkdir -p $LOGDIR/{step2b,step3a,step3b}
touch $MAINLOG
touch $STEP3LOG
chown -R $FIXIT123_USER.$FIXIT123_USER $LOGDIR
chmod -R ug+rw $LOGDIR
