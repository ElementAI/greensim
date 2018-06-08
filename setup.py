from setuptools import setup
from subprocess import check_output

setup(
    name='sim',
    version=check_output(("git", "describe", "--tags"), universal_newlines=True).strip(),
    packages=['sim'],
    install_requires=['greenlet==0.4.13'],
    description='Discrete Event Simulator',
    long_description=open('README.md').read()
)
