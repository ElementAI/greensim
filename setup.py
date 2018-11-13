from setuptools import setup
# from subprocess import check_output

with open("README.md", "r") as file_long_description:
    long_description = file_long_description.read()

setup(
    name='greensim',
    maintainer="Benoit Hamelin",
    maintainer_email="ben@elementai.com",
    version='2.3.0',
    packages=['greensim'],
    data_files=[('.', ['LICENSE'])],
    install_requires=['greenlet==0.4.14'],
    description='Discrete event simulation toolkit based on greenlets',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ElementAI/greensim",
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent"
    )
)
