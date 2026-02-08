# vim: syntax=make

srcsubdir := $(notdir $(shell pwd))
binstatus:
	@-[ -f .binstatus ] && /bin/rm -f .binstatus
	@for tgtbin in $(INSTALLTARGETS); do \
		if [ ! -x $$tgtbin ]; then \
			tput setaf 1 >> .binstatus; tput bold >> .binstatus; \
			echo "SOURCE SUBDIR $(srcsubdir): $$tgtbin was not built" >> .binstatus; \
			tput sgr0 >> .binstatus;\
		else \
			tput setaf 2 >> .binstatus; tput bold >> .binstatus; \
			echo "SOURCE SUBDIR $(srcsubdir): $$tgtbin was built ok" >> .binstatus; \
			tput sgr0 >> .binstatus;\
		fi; \
	done


