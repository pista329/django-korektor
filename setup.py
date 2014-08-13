#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name="django-korektor",
    version='0.1.4',
    url='http://github.com/pista329/django-korektor',
    author='Stefan Backor',
    author_email='stefan@backor.sk',
    description='Google like "Did you mean" '
                'spellcheck proof of concept for Django app.',
    packages=find_packages(exclude='testapp'),
    install_requires=[
        'django>=1.6.5',
        'ordereddict>=1.0',
        'unidecode>=0.04.9'
    ],
    license='MIT',
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Framework :: Django",
        "Environment :: Web Environment",
        "Operating System :: OS Independent",
        "Natural Language :: English",
    ]
)