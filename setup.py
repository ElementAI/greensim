from setuptools import setup
from subprocess import check_output

    # version=check_output(("git", "describe", "--tags"), universal_newlines=True).strip(),
setup(
    name='sim',
    version='1.0.1',
    packages=['sim'],
    install_requires=['greenlet==0.4.13'],
    description='Discrete Event Simulator',
    long_description=open('README.md').read()
)
