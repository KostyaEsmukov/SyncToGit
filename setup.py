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
    install_requires=[
        "GitPython==2.1.11",
        "click==6.7",
        "defusedxml==0.5.0",
        "evernote3==1.25.12",
        "jinja2==2.10",
        "oauth2==1.9.0.post1",
        "regex==2018.08.29",
    ],
    extras_require={
        'dev': [
            'coverage==4.5.1',
            'flake8==3.5.0',
            'isort==4.3.4',
            'pytest==3.8.1',
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
