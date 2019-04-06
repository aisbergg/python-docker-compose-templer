#!/usr/bin/env python3

from os import path

from setuptools import setup, find_packages

with open(path.join(path.abspath(path.dirname(__file__)), 'README.md')) as f:
    long_description = f.read()

setup(
    name='Docker Compose Templer',
    version='1.1.0',
    author='Andre Lehmann',
    author_email='aisberg@posteo.de',
    url='https://github.com/Aisbergg/python-docker-compose-templer',
    license='LGPL',
    description='Render Docker Compose file templates with the power of Jinja2',
    long_description=long_description,
    long_description_content_type='text/markdown',
    keywords='Jinja2 templating command-line CLI "Docker-Compose"',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: System :: Systems Administration',
        'Topic :: Utilities',
    ],
    project_urls={
        'Bug Reports': 'https://github.com/Aisbergg/python-docker-compose-templer/issues',
        'Source': 'https://github.com/Aisbergg/python-docker-compose-templer',
    },
    packages=find_packages(exclude=['examples', 'tests']),
    scripts=[
        'bin/docker-compose-templer'
    ],
    install_requires=[
        'jinja2',
        'ruamel.yaml'
    ],
    extras_require={
        'AutoRenderer': ["pyinotify"],
    },
    include_package_data=True,
    zip_safe=False,
    platforms=['POSIX'],
)
