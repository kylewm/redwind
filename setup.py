#!/usr/bin/env python
import sys
from distutils.core import setup
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.pytest_args)
        sys.exit(errno)


setup(name='Red Wind',
      version='0.1',
      description='IndieWeb-ready personal website software',
      author='Kyle Mahan',
      author_email='kyle@kylewm.com',
      url='https://indiewebcamp.com/Red_Wind',
      packages=['redwind', 'redwind.plugins'],
      tests_require=['pytest'],
      cmdclass={'test': PyTest})
