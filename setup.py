#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
from setuptools import setup

import synctogit

version = synctogit.__version__

if sys.argv[-1] == 'publish':
    os.system('python setup.py sdist upload --sign')
    print("You probably want to also tag the version now:")
    print("  git tag -s -a v%s" % version)
    print("  git push --tags")
    sys.exit()


def strip_comments(l):
    return l.split('#', 1)[0].strip()


def reqs(*f):
    return [r for r in (strip_comments(lr) for l in (open(os.path.join(os.getcwd(), ff)).readlines() for ff in f) for lr in l) if r]


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
    packages=[
        'synctogit',
    ],
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'synctogit = synctogit.main:main'
        ]
    },
    install_requires=reqs("requirements"),
    license="MIT",
    zip_safe=False,
    keywords='evernote backup git',
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2.7',
        'Topic :: Utilities'
    ],
)
