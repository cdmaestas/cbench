if [ ! -z $FIXIT123_CONF ]; then
        eval `grep -v '^[:blank:]*#' $FIXIT123_CONF | sed 's|\([^=]*\)=\([^=]*\)|export \1=\2|g' | sed 's|$||'`
elif [ -f /etc/sysconfig/fixit123 ]; then
        eval `grep -v '^[:blank:]*#' /etc/sysconfig/fixit123 | sed 's|\([^=]*\)=\([^=]*\)|export \1=\2|g' | sed 's|$||'`
		export FIXIT123_CONF=/etc/sysconfig/fixit123
else
    echo "fixit123 configuration not defined!"
    echo "I hope you have set proper environmental variables!"
fi

if [ -z $NODECHECKS_HOME ]; then
	export NODECHECKS_HOME=$FIXIT123_HOME/libexec/nodechecks
fi
