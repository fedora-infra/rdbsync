from setuptools import setup, find_packages


setup(
    name='rdbsync',
    description='Sync ResultsDB instances using the REST API.',
    version='0.1.0',
    author='Red Hat, Inc. and others',
    author_email='infrastructure@fedoraproject.org',
    maintainer='Red Hat, Inc. and others',
    maintainer_email='infrastructure@fedoraproject.org',
    license='GPLv2+',
    packages=find_packages(),
    include_package_data=True,
    install_requires=['requests', 'click'],
    tests_require=['pytest', 'betamax'],
    classifiers=[  # https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    entry_points="""
        [console_scripts]
        rdbsync=rdbsync:cli
    """
)
