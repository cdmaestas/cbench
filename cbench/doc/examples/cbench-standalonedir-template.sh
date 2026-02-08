# the required variables
export CBENCHSTANDALONEDIR=REPLACE_CBENCHSTANDALONEDIR
export CBENCHOME=REPLACE_CBENCHOME

export PATH=$CBENCHSTANDALONEDIR/openmpi/bin:$PATH
export LD_LIBRARY_PATH=$CBENCHSTANDALONEDIR/OpenBLAS/lib/:$CBENCHSTANDALONEDIR/openmpi/lib:$LD_LIBRARY_PATH
export BLASLIB="-L$CBENCHSTANDALONEDIR/OpenBLAS/lib -lopenblas -lgfortran -lm"
export LAPACKLIB="-L$CBENCHSTANDALONEDIR/OpenBLAS/lib -lopenblas"

# add the Cbench tools directory to the path to pickup
# cbench commands more easily
export PATH=$PATH:$CBENCHOME/tools

# a favorite alias for seeing what Cbench env looks like
alias showcb='env | grep --color=always -e CBENCH -e MPIHOME -e COMPILER -e RPATH -e BLASLIB -e FFTW -e LAPACK'

