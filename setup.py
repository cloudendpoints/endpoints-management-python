#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import re

from setuptools import setup, find_packages

# Get the version
version_regex = r'__version__ = ["\']([^"\']*)["\']'
with open('endpoints_management/__init__.py', 'r') as f:
    text = f.read()
    match = re.search(version_regex, text)
    if match:
        version = match.group(1)
    else:
        raise RuntimeError("No version number found!")

install_requires = [
    'cachetools>=1.0.0,<2',
    "dogpile.cache>=0.6.1,<0.7",
    'enum34>=1.1.6,<2',
    'google-apitools',
    'oauth2client>=2.0.0,<4.0.0dev',
    'ply>=3.8,<4.0',
    "pylru>=1.0.9,<2.0",
    "pyjwkest>=1.0.0,<=1.0.9",
    "requests>=2.10.0,<3.0",
    'strict-rfc3339>=0.7,<0.8',
    'urllib3>=1.16,<2.0',
]

dependency_links = [
    'http://github.com/inklesspen/apitools/tarball/endpoints-dependency#egg=google-apitools-0.5.15dev0'
]

tests_require = [
    "flask>=0.11.1",
    "httmock>=1.2",
    "mock>=2.0",
    "pytest",
    "pytest-cov"
]

setup(
    name='google-endpoints-api-management',
    version=version,
    description='Google Endpoints API management',
    long_description=open('README.rst').read(),
    author='Google Inc',
    author_email='googleapis-packages@google.com',
    url='https://github.com/cloudendpoints/endpoints-management-python',
    packages=find_packages(),
    namespace_packages=[],
    package_dir={'google-endpoints-api-management': 'endpoints_management'},
    license='Apache License',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
    install_requires=install_requires,
    dependency_links=dependency_links,
    setup_requires=["pytest_runner"],
    tests_require=tests_require,
    test_suite="tests"
)
