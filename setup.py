#!/usr/bin/env python
# -*- coding: utf-8 -*-


from setuptools import setup


with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('requirements.txt') as req_file:
    requirements = req_file.read().split('\n')

with open('requirements-dev.txt') as req_file:
    requirements_dev = req_file.read().split('\n')

with open('VERSION') as fp:
    version = fp.read().strip()

setup(
    name='wabclient',
    version=version,
    description="WhatsApp Business API Client",
    long_description=readme,
    author="Simon de Haan",
    author_email='simon@praekelt.org',
    url='https://github.com/praekeltfoundation/python-whatsapp-business-client',  # noqa
    packages=[
        'wabclient',
    ],
    package_dir={'wabclient':
                 'wabclient'},
    extras_require={
        'dev': requirements_dev,
    },
    include_package_data=True,
    install_requires=requirements,
    entry_points={},
    zip_safe=False,
    keywords='whatsapp',
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
    ]
)
