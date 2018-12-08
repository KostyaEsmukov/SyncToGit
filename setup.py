#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import find_packages, setup

import synctogit

version = synctogit.__version__

readme = open('README.rst').read()
changelog = open('CHANGELOG.rst').read()

setup(
    name='synctogit',
    version=version,
    description="Syncs Evernote(R) notes to a git repository in HTML.",
    long_description=readme + '\n\n' + changelog,
    author='Kostya Esmukov',
    author_email='kostya@esmukov.ru',
    url='https://github.com/KostyaEsmukov/SyncToGit',
    packages=find_packages(exclude=["*test*"]),
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'synctogit = synctogit.__main__:synctogit'
        ]
    },
    install_requires=[
        "GitPython>=2.1.11,<3",
        "cached-property",
        "click>=6",
        "configupdater>=0.3.2,<1",
        "defusedxml>=0.5.0,<1",
        "jinja2>=2,<3",
        "prompt_toolkit>=2,<3",
        "python-dateutil>=2.7.0,<3",
        "pytz",
        "regex",
        "tzlocal",
    ],
    extras_require={
        'dev': [
            'coverage==4.5.1',
            'flake8==3.5.0',
            'isort==4.3.4',
            'pytest==3.8.1',
            'vcrpy==2.0.0',
        ],
        'todoist': [
            'todoist-python==7.0.18',
        ],
        'evernote': [
            "evernote3==1.25.12",
            "oauth2==1.9.0.post1",
        ],
        'onenote': [
            "beautifulsoup4>=4.6,<5",
            "oauth2==1.9.0.post1",
            "requests_toolbelt>=0.8.0,<1",
        ],
    },
    license="MIT",
    python_requires=">=3.5",
    zip_safe=False,
    keywords='evernote backup git',
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3 :: Only",
        'Topic :: Utilities',
    ],
)
