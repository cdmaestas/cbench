c iq.h
c Defines per node tile size for the computational mesh.
c
c Following settings are for 200x200x350 total
c problem size with a 1x1x1 nodelayout.
c
c This problem size should use <=1.4 GB of memory per core

define(IQX, 200)
define(IQY, 200)
define(IQZ, 200)

c IQ should be set to at least the max of IQX, IQY, & IQZ
define(IQ, 200)


