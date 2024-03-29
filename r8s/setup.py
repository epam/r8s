# Copyright 2018 EPAM Systems, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# [http://www.apache.org/licenses/LICENSE-2.0]
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from setuptools import find_packages, setup
from __version__ import __version__


setup(
    name='r8s',
    version=__version__,
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click==7.1.2',
        'PyYAML==6.0.1',
        'tabulate==0.9.0',
        'requests==2.31.0',
        'prettytable==3.9.0',
        'modular-cli-sdk>=2.0.0,<3.0.0'
    ],
    entry_points='''
        [console_scripts]
        r8s=r8s_group.r8s:r8s
    ''',
)
