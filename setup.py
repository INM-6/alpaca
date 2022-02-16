import os

from setuptools import setup

with open(os.path.join(os.path.dirname(__file__),
                       "alpaca", "VERSION")) as version_file:
    version = version_file.read().strip()

with open("README.md") as f:
    long_description = f.read()

with open('requirements/requirements.txt') as fp:
    install_requires = fp.read()


setup(
    name="alpaca",
    version=version,
    packages=['alpaca', 'alpaca.utils'],
    include_package_data=True,
    install_requires=install_requires,
    author="Alpaca authors and contributors",
    author_email="",
    description="Alpaca is a package for the capture of provenance "
                "information during the execution of data analysis workflows "
                "based on Python scripts and Jupyter notebooks",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="BSD",
    url='https://github.com/INM-6/alpaca',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering']
)
