#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

from setuptools import setup

if sys.version_info < (3, 5):
    # Courtesy of https://python3statement.org/practicalities/
    raise ImportError(
        """You are running synctogit on an unsupported
version of Python.

synctogit 3.0 and above are no longer compatible with Python <3.5, and you still
ended up with this version installed. That's unfortunate; sorry about that.
It should not have happened. Make sure you have pip >= 9.0 to avoid this kind
of issue, as well as setuptools >= 24.2:

 $ pip install pip setuptools --upgrade

Your choices:

- Upgrade to Python 3.5.

- Install an older version of synctogit:

 $ pip install 'synctogit<3.0'
"""
    )


setup()
