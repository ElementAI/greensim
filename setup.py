from setuptools import setup

setup(
    name='sim',
    version='1.0.0',
    packages=['sim'],
    install_requires=['greenlet==0.4.13'],
    description='Discrete Event Simulator',
    long_description=open('README.md').read()
)
