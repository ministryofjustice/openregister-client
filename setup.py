import importlib
import os
import sys
import warnings

from setuptools import find_packages, setup

if sys.version_info[0:2] < (3, 6):
    warnings.warn('This package will only run on Python version 3.6+')

root_path = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(root_path, 'README.rst')) as readme:
    README = readme.read()

install_requires = ['requests']
extras_require = {
    'django': ['django'],
    'pytz': ['pytz'],
    'markdown': ['Markdown'],
}
tests_require = ['flake8', 'responses']

package_info = importlib.import_module('openregister_client')

setup(
    name='openregister-client',
    version=package_info.__version__,
    author=package_info.__author__,
    author_email='dev@digital.justice.gov.uk',
    url='https://github.com/ministryofjustice/openregister-client',
    packages=find_packages(exclude=['tests']),
    include_package_data=True,
    license='MIT',
    description='A client for reading data from Registers provided by Government Digital Services',
    long_description=README,
    keywords='openregister govuk',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    install_requires=install_requires,
    extras_require=extras_require,
    tests_require=tests_require,
    test_suite='tests',
)
