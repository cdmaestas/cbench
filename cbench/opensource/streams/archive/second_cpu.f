c
c     wrapper for gettimeofday()
c
      DOUBLE PRECISION function mysecond(dummy)
      implicit none
      double precision dummy, tstamp
      external gettimestamp
      call gettimestamp(tstamp)
      mysecond = tstamp
      END

