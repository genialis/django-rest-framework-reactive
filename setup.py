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
    python_requires='>=3.6, <3.10',
    install_requires=[
        'Django~=3.0',
        'djangorestframework~=3.12.2',
        'channels~=3.0.3',
    ],
    extras_require={
        'docs': ['sphinx', 'sphinx_rtd_theme'],
        'package': ['twine', 'wheel'],
        'test': [
            'django-filter~=2.4',
            'django-guardian>=2.3',
            'django-priority-batch >=3.0a1, ==3.*',
            'channels-redis~=3.2.0',
            'pytest>=4.4.1',
            'pytest-django>=3.4.8',
            'pytest-asyncio>=0.10.0',
            'async_timeout~=3.0.1',
            'psycopg2-binary~=2.8.6',
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
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    keywords='django-rest-framework reactive django',
)
