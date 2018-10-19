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
    python_requires='>=3.6',
    install_requires=[
        'Django~=1.11.6',
        'djangorestframework>=3.4.0',
        'channels~=2.1.1',
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
            'djangorestframework-filters~=0.10.0',
            # XXX: djangorestframework-filters has too open requirement for
            # django-filter and doesn't work with the latest version, so we
            # have to pin it
            'django-filter~=1.0.0',
            'django-guardian>=1.4.2',
            'django-jenkins>=0.17.0',
            'django-priority-batch>=1.0.0',
            'channels-redis~=2.1.0',
            'coverage>=3.7.1',
            'pep8>=1.6.2',
            'pylint>=1.4.3',
            'pytest~=3.5.1',
            'pytest-django~=3.2.1',
            'pytest-asyncio~=0.8.0',
            'async_timeout>=2.0,<4.0',
            'psycopg2>=2.5.0',
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
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],

    keywords='django-rest-framework reactive django',
)
