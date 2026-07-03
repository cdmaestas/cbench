PACKAGE  = cbench
VERSION  = 2.0.0
RELEASE  = 1

# Directories
PKGDIR   = $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
SRCDIR   = $(abspath $(PKGDIR)/..)
STAGEDIR = $(PKGDIR)_stage
OUTDIR   = $(PKGDIR)_dist

.PHONY: all fpm-rpm fpm-deb native-rpm native-deb stage clean-stage clean help

all: fpm-rpm fpm-deb

help:
	@echo "Targets:"
	@echo "  fpm-rpm     Build RPM via fpm (bundles all Python deps)"
	@echo "  fpm-deb     Build DEB via fpm (bundles all Python deps)"
	@echo "  native-rpm  Build RPM via rpmbuild (uses system Python packages)"
	@echo "  native-deb  Build DEB via dpkg-buildpackage (uses system Python packages)"
	@echo "  all         fpm-rpm + fpm-deb"
	@echo "  clean       Remove build artefacts"

# ---------------------------------------------------------------------------
# Shared staging step for fpm builds
# pip install --target bundles cbench + all runtime deps (including flask/web)
# ---------------------------------------------------------------------------
stage: clean-stage
	@mkdir -p "$(STAGEDIR)/usr/lib/cbench" "$(STAGEDIR)/usr/bin"
	pip3 install --quiet \
	    --target "$(STAGEDIR)/usr/lib/cbench" \
	    "$(SRCDIR)[web]"
	install -m 755 "$(PKGDIR)cbench.wrapper" "$(STAGEDIR)/usr/bin/cbench"

# ---------------------------------------------------------------------------
# fpm targets — require: gem install fpm  (or pip install fpm)
# ---------------------------------------------------------------------------
fpm-rpm: stage | $(OUTDIR)
	fpm -s dir -t rpm \
	    -n $(PACKAGE) \
	    -v $(VERSION) \
	    --iteration $(RELEASE) \
	    --architecture noarch \
	    --description "Cbench HPC benchmarking framework — Python toolchain" \
	    --url "https://github.com/cdmaestas/cbench" \
	    --license "GPLv2" \
	    --depends "python3 >= 3.9" \
	    --rpm-summary "cbench HPC benchmark CLI" \
	    -C "$(STAGEDIR)" \
	    --package "$(OUTDIR)/$(PACKAGE)-$(VERSION)-$(RELEASE).noarch.rpm" \
	    .
	@echo "Built: $(OUTDIR)/$(PACKAGE)-$(VERSION)-$(RELEASE).noarch.rpm"

fpm-deb: stage | $(OUTDIR)
	fpm -s dir -t deb \
	    -n $(PACKAGE) \
	    -v $(VERSION) \
	    --iteration $(RELEASE) \
	    --architecture all \
	    --description "Cbench HPC benchmarking framework — Python toolchain" \
	    --url "https://github.com/cdmaestas/cbench" \
	    --license "GPLv2" \
	    --depends "python3 (>= 3.9)" \
	    -C "$(STAGEDIR)" \
	    --package "$(OUTDIR)/$(PACKAGE)_$(VERSION)-$(RELEASE)_all.deb" \
	    .
	@echo "Built: $(OUTDIR)/$(PACKAGE)_$(VERSION)-$(RELEASE)_all.deb"

# ---------------------------------------------------------------------------
# native-rpm — requires rpmbuild; uses system Python packages for deps
# ---------------------------------------------------------------------------
native-rpm: | $(OUTDIR)
	rpmbuild -bb \
	    --define "_rpmdir $(OUTDIR)" \
	    --define "_builddir /tmp/cbench-rpmbuild-$(VERSION)" \
	    --define "cbench_srcdir $(SRCDIR)" \
	    --define "cbench_pkgdir $(PKGDIR)" \
	    "$(PKGDIR)cbench.spec"
	@echo "Built RPM in $(OUTDIR)/"

# ---------------------------------------------------------------------------
# native-deb — requires dpkg-buildpackage + dh-python; uses system packages
# Copies debian/ into the source tree temporarily, builds, then cleans up.
# ---------------------------------------------------------------------------
native-deb: | $(OUTDIR)
	cp -r "$(PKGDIR)debian" "$(SRCDIR)/debian"
	cd "$(SRCDIR)" && dpkg-buildpackage -us -uc -b \
	    --buildinfo-option=-O \
	    --changes-option=-O
	rm -rf "$(SRCDIR)/debian"
	mv "$(SRCDIR)"/../$(PACKAGE)_*.deb "$(OUTDIR)/" 2>/dev/null || \
	    mv "$(SRCDIR)"/../$(PACKAGE)-*.deb "$(OUTDIR)/" 2>/dev/null || true
	@echo "Built DEB in $(OUTDIR)/"

$(OUTDIR):
	mkdir -p "$(OUTDIR)"

clean-stage:
	rm -rf "$(STAGEDIR)"

clean: clean-stage
	rm -rf "$(OUTDIR)"
	rm -rf "$(SRCDIR)/debian"
