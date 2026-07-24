PACKAGE  = cbench
VERSION  ?= 2.0.0
RELEASE  = 1

# Install paths (on target system)
LIBDIR   = /usr/lib/cbench
BINDIR   = /usr/bin
MANDIR   = /usr/share/man/man1
DOCDIR   = /usr/share/doc/cbench

# Build directories
PKGDIR   = $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
SRCDIR   = $(abspath $(PKGDIR)/..)
REPODIR  = $(abspath $(SRCDIR)/../..)
STAGEDIR = $(PKGDIR)_stage
MANSTAGE = $(PKGDIR)_manbuild
OUTDIR   = $(PKGDIR)_dist

.PHONY: all fpm-rpm fpm-deb native-rpm native-deb man stage clean-stage clean help

all: fpm-rpm fpm-deb

help:
	@echo "Targets:"
	@echo "  fpm-rpm     Build RPM via fpm (bundles all Python deps)"
	@echo "  fpm-deb     Build DEB via fpm (bundles all Python deps)"
	@echo "  native-rpm  Build RPM via rpmbuild (uses system Python packages)"
	@echo "  native-deb  Build DEB via dpkg-buildpackage (uses system Python packages)"
	@echo "  man         Generate man pages into _stage$(MANDIR)"
	@echo "  all         fpm-rpm + fpm-deb"
	@echo "  clean       Remove all build artefacts"

# ---------------------------------------------------------------------------
# Man page generation
# Installs cbench + click-man into a temporary --target dir (no venv needed),
# then generates one .1 file per Click command under the staging man dir.
# ---------------------------------------------------------------------------
man:
	@echo "Generating man pages..."
	rm -rf "$(MANSTAGE)"
	mkdir -p "$(STAGEDIR)$(MANDIR)"
	pip3 install --quiet --target "$(MANSTAGE)" "$(SRCDIR)" "click-man>=0.4"
	PYTHONPATH="$(MANSTAGE)" python3 "$(PKGDIR)gen_manpages.py" \
	    "$(STAGEDIR)$(MANDIR)"
	gzip -f "$(STAGEDIR)$(MANDIR)"/*.1
	rm -rf "$(MANSTAGE)"

# ---------------------------------------------------------------------------
# Shared staging step (used by fpm builds)
# pip install --target bundles cbench + all runtime deps (including flask/web)
# ---------------------------------------------------------------------------
# In CI the man pages are pre-downloaded into _stage/usr/share/man by the
# 'man' job; skip regeneration if they're already present.
stage: clean-stage
	@if [ ! -d "$(STAGEDIR)$(MANDIR)" ]; then $(MAKE) man; fi
	mkdir -p "$(STAGEDIR)$(LIBDIR)" "$(STAGEDIR)$(BINDIR)" "$(STAGEDIR)$(DOCDIR)"
	pip3 install --quiet \
	    --target "$(STAGEDIR)$(LIBDIR)" \
	    "$(SRCDIR)[web]"
	install -m 755 "$(PKGDIR)cbench.wrapper" "$(STAGEDIR)$(BINDIR)/cbench"
	install -m 644 "$(REPODIR)/README.md"    "$(STAGEDIR)$(DOCDIR)/README.md"
	install -m 644 "$(REPODIR)/CHANGELOG.md" "$(STAGEDIR)$(DOCDIR)/CHANGELOG.md"

# ---------------------------------------------------------------------------
# fpm targets — require: gem install fpm
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
#
# RPMBUILD_FLAGS lets callers pass extra rpmbuild options. When cross-building
# on a non-RPM distro (e.g. Ubuntu in CI) the RPM database is empty, so the
# BuildRequires can never be satisfied there and callers should pass
# RPMBUILD_FLAGS=--nodeps. Left empty by default so real RHEL/Rocky builds
# still get proper build-dependency checking.
# ---------------------------------------------------------------------------
native-rpm: | $(OUTDIR)
	rpmbuild -bb $(RPMBUILD_FLAGS) \
	    --define "_rpmdir $(OUTDIR)" \
	    --define "_builddir /tmp/cbench-rpmbuild-$(VERSION)" \
	    --define "cbench_srcdir $(SRCDIR)" \
	    --define "cbench_pkgdir $(PKGDIR)" \
	    --define "cbench_repodir $(REPODIR)" \
	    "$(PKGDIR)cbench.spec"
	@echo "Built RPM in $(OUTDIR)/"

# ---------------------------------------------------------------------------
# native-deb — requires dpkg-buildpackage + dh-python
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
	rm -rf "$(STAGEDIR)" "$(MANSTAGE)"

clean: clean-stage
	rm -rf "$(OUTDIR)"
	rm -rf "$(SRCDIR)/debian"
