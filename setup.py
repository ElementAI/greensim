from setuptools import setup
# from subprocess import check_output

# version=check_output(("git", "describe", "--tags"), universal_newlines=True).strip(),
setup(
    name='greensim',
    version='1.1.2',
    packages=['greensim'],
    install_requires=['greenlet==0.4.13'],
    description='Discrete event simulation toolkit based on greenlets',
    long_description=open('README.md').read()
)
