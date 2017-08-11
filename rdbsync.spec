
Name:           rdbsync
Version:        0.3.0
Release:        1%{?dist}
Summary:        A script to sync CentOS CI ResultsDB to Fedora

License:        GPLv2
URL:            https://github.com/jeremycline/%{name}
Source0:        %{url}/archive/%{version}/%{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires: python2-devel
BuildRequires: python2-setuptools
BuildRequires: systemd
Requires: python2-requests
Requires: python2-click

%description
A script to sync CentOS CI ResultsDB to Fedora.


%prep
%autosetup


%build
%py2_build


%install
%py2_install
install -p -D -T -m 0644 rdbsync.service %{buildroot}/%{_unitdir}/rdbsync.service


%files
%license LICENSE
%doc README.md
%{_bindir}/rdbsync
%{_unitdir}/rdbsync.service
%{python2_sitelib}/%{name}
%{python2_sitelib}/%{name}-*.egg-info


%changelog
* Fri Aug 11 2017 Jeremy Cline <jeremy@jcline.org> - 0.3.0-1
- Update to latest upstream

* Thu Aug 10 2017 Jeremy Cline <jeremy@jcline.org> - 0.1.0-1
- Initial package
