import os.path
import setuptools

# Get long description from README.
with open('README.rst', 'r') as fh:
    long_description = fh.read()

# Get package metadata from '__about__.py' file.
about = {}
base_dir = os.path.abspath(os.path.dirname(__file__))
with open(
    os.path.join(base_dir, 'src', 'rest_framework_reactive', '__about__.py'), 'r'
) as fh:
    exec(fh.read(), about)

setuptools.setup(
    name=about['__title__'],
    use_scm_version=True,
    description=about['__summary__'],
    long_description=long_description,
    long_description_content_type='text/x-rst',
    author=about['__author__'],
    author_email=about['__email__'],
    url=about['__url__'],
    license=about['__license__'],
    # Exclude tests from built/installed package.
    packages=setuptools.find_packages(
        'src', exclude=['tests', 'tests.*', '*.tests', '*.tests.*']
    ),
    package_dir={'': 'src'},
    python_requires='>=3.6, <3.7',
    install_requires=[
        'Django~=1.11.6',
        'djangorestframework>=3.4.0',
        'channels~=2.1.1',
    ],
    extras_require={
        'docs': ['sphinx>=1.3.2', 'sphinx_rtd_theme'],
        'package': ['twine', 'wheel'],
        'test': [
            'djangorestframework-filters~=0.10.0',
            # XXX: djangorestframework-filters has too open requirement for
            # django-filter and doesn't work with the latest version, so we
            # have to pin it
            'django-filter~=1.0.0',
            'django-guardian>=1.4.2',
            'django-priority-batch>=1.0.0',
            'channels-redis~=2.1.0',
            'pylint>=1.4.3',
            'pytest~=3.5.1',
            'pytest-django~=3.2.1',
            'pytest-asyncio~=0.8.0',
            'async_timeout>=2.0,<4.0',
            'psycopg2>=2.5.0',
            'check-manifest',
            'twine',
            'setuptools_scm',
            'black',
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
