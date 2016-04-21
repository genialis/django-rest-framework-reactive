#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Making Django REST Framework reactive.

See:
https://github.com/genialis/django-rest-framework-reactive
"""

from setuptools import find_packages, setup
# Use codecs' open for a consistent encoding
from codecs import open
from os import path

base_dir = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(base_dir, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

# Get package metadata from 'rest_framework_reactive.__about__.py' file
about = {}
with open(path.join(base_dir, 'rest_framework_reactive', '__about__.py'), encoding='utf-8') as f:
    exec(f.read(), about)

setup(
    name=about['__title__'],

    version=about['__version__'],

    description=about['__summary__'],
    long_description=long_description,

    url=about['__url__'],

    author=about['__author__'],
    author_email=about['__email__'],

    license=about['__license__'],

    packages=find_packages(exclude=['tests']),
    install_requires=[
        'django>=1.9,<1.10a1',
        # XXX: djangorestframework 3.3.3 fails to install on Read the Docs
        # Bug report: https://github.com/rtfd/readthedocs.org/issues/2101
        'djangorestframework==3.3.2',
        'psycopg2>=2.5.0',
        'gevent>=1.0.2',
        'psycogreen>=1.0',
        'django-db-geventpool>=1.20.1',
        'redis>=2.10.5',
        'requests>=2.8.1',
        'django-websocket-redis>=0.4.6',
        'django-redis>=4.3.0'
    ],
    extras_require={
        'docs': [
            'sphinx>=1.3.2',
            'sphinx_rtd_theme',
        ],
        'package': [
            'twine',
            'wheel',
        ],
        'test': [
            'django-guardian==1.3.2',
            'django-jenkins>=0.17.0',
            'coverage>=3.7.1',
            'pep8>=1.6.2',
            'pylint>=1.4.3',
            'check-manifest',
            'readme',
        ],
    },

    classifiers=[
        'Development Status :: 4 - Beta',

        'Environment :: Web Environment',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Internet :: WWW/HTTP :: WSGI',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Software Development :: Libraries :: Python Modules',

        'License :: OSI Approved :: Apache Software License',

        'Operating System :: OS Independent',

        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ],

    keywords='django-rest-framework reactive django',
)
