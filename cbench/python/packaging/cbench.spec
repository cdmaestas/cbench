Name:           cbench
Version:        2.0.0
Release:        1%{?dist}
Summary:        Cbench HPC benchmarking framework — Python toolchain
License:        GPLv2
URL:            https://github.com/cdmaestas/cbench
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-pip

# Runtime: use distro-provided Python packages rather than bundling.
# For RHEL/Rocky 8+: dnf install python3-click python3-pyyaml python3-rich
#                                  python3-jinja2 python3-jsonschema
# Flask (web dashboard) is optional — install separately if needed.
Requires:       python3 >= 3.9
Requires:       python3-click >= 8.1
Requires:       python3-pyyaml >= 6.0
Requires:       python3-rich >= 13.0
Requires:       python3-jinja2 >= 3.1
Requires:       python3-jsonschema >= 4.0

# Optional: web dashboard
# Requires:     python3-flask >= 2.0

%description
Cbench is an HPC benchmarking framework originally developed at Sandia
National Laboratories. The Python toolchain (v2.0) provides a cbench
CLI for the full benchmark lifecycle: build benchmark software, generate
job scripts, submit to a batch scheduler, parse output, query results,
run single-node benchmarks, and serve a web dashboard.

%install
install -d %{buildroot}/usr/lib/cbench

# Install only cbench itself (no bundled deps — distro packages handle them).
pip3 install --quiet --no-deps \
    --target %{buildroot}/usr/lib/cbench \
    %{cbench_srcdir}

# Strip the buildroot prefix from any embedded paths.
find %{buildroot}/usr/lib/cbench -name "*.py" \
    -exec sed -i "s|%{buildroot}||g" {} \; 2>/dev/null || true

install -D -m 755 %{cbench_pkgdir}/cbench.wrapper %{buildroot}/usr/bin/cbench

%files
/usr/lib/cbench/
/usr/bin/cbench

%changelog
* Thu Jul 03 2026 cdmaestas <cdmaestas@gmail.com> - 2.0.0-1
- Initial v2.0 package release.
