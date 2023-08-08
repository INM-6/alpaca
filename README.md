# alpaca

## Automated Lightweight Provenance Capture

[![tests](https://github.com/INM-6/alpaca/actions/workflows/CI.yml/badge.svg)](https://github.com/INM-6/alpaca/actions/workflows/CI.yml)
[![Documentation Status](https://readthedocs.org/projects/alpaca-prov/badge/?version=latest)](https://alpaca-prov.readthedocs.io/en/latest/?badge=latest)

Alpaca is a Python package for the capture of provenance information during the
execution of Python scripts that process data.

Alpaca provides a simple API for recording the details of the functions being
executed, the data flow, and a description of parameters used.
This is accomplished with minimal code instrumentation and user intervention.

Provenance information is structured and serialized according to a model
based on the [W3C PROV format](https://www.w3.org/TR/prov-overview).


## Table of contents
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Documentation](#documentation)
  - [How to run](#how-to-run)
  - [Collaborators](#collaborators)
  - [How to contribute](#how-to-contribute)
  - [Get support](#get-support)
  - [Acknowledgments](#acknowledgments)
  - [License](#license)
  - [Copyright](#copyright)


## Prerequisites

### Requirements

Alpaca requires Python 3.8 or higher and the packages specified in 
[requirements.txt](requirements/requirements.txt).


## Installation

Use the package manager [pip](https://pip.pypa.io/en/stable/) to install Alpaca.

Package on [pypi](https://pypi.org/)
```bash
pip install alpaca-prov
```

More detailed instructions on how to setup conda environments and additional
install options can be checked in the [Installation](doc/install.rst) page.


## Documentation

See [https://alpaca-prov.readthedocs.io/en/latest/](https://alpaca-prov.readthedocs.io/en/latest/).


## How to run

Examples showing how to use Alpaca can be found in the [examples](examples/)
folder. Detailed instructions on how to set up and run are 
[here](doc/examples.rst).


## Colaborators

All the contributors to the development of Alpaca can be found in the 
[Authors and contributors](doc/authors.rst) page.


## How to contribute

If you want to suggest new features, changes, or make a contribution, please
first open an issue on the [project page on GitHub](https://github.com/INM-6/alpaca/issues)
to discuss your idea.

Pull requests are welcome. Any contribution should also
be covered by appropriate unit tests in the [tests](alpaca/test) folder.


## Get support

If you experience any issue or wish to report a bug, please open an issue on
the [project page on GitHub](https://github.com/INM-6/alpaca/issues).


## Acknowledgments

See [acknowledgments](doc/acknowledgments.rst).


## License
 
BSD 3-Clause License, see [LICENSE.txt](LICENSE.txt) for details.


## Copyright

:copyright: 2022-2023, Forschungszentrum Jülich GmbH, INM-6, IAS-6. All rights reserved.