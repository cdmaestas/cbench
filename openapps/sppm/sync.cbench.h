      parameter (iperim1chnk = (iq+nrows-1)/nrows)
      parameter (iperim2chnk = (iq+mrows-1)/mrows)
      parameter (iperimchnk = iperim1chnk + iperim2chnk)
      parameter(ibinsize=2*iperimchnk+nxyzchnk*nxyzchnk)
      common / fastio / num_boundary(6), num_boundary2(6),
     &    num_boundary0(6), num_perimeter1(6), ibins(2,2,ibinsize,6),
     &    icomm_point(6,6), num_bins(6), kbdrysplit(6)
      common / volit /iflag,istate,idone(ibinsize)
