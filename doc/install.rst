.. _install:

************
Installation
************

The easiest way to install Alpaca is by creating a
`conda <https://conda.io/>`_ environment, followed by install using `pip`.
Below is the explanation of how to proceed with these two steps.


Prerequisites
=============

Alpaca requires `Python <http://python.org/>`_ 3.8 or higher.

.. tabs::


    .. tab:: (recommended) Conda (Linux/MacOS/Windows)

        1. Create your conda environment (e.g., `alpaca`):

           .. code-block:: sh

              conda create --name alpaca python=3.11

        2. Activate your environment:

           .. code-block:: sh

              conda activate alpaca


    .. tab:: Debian/Ubuntu

        Open a terminal and run:

        .. code-block:: sh

           sudo apt-get install python-pip


Installation
============

.. tabs::

    .. tab:: Stable release version

        The easiest way to install Alpaca is via `pip
        <http://pypi.python.org/pypi/pip>`_:

           .. code-block:: sh

              pip install alpaca-prov

        To upgrade to a newer release use the ``--upgrade`` flag:

           .. code-block:: sh

              pip install --upgrade alpaca-prov

        If you do not have permission to install software systemwide, you can
        install into your user directory using the ``--user`` flag:

           .. code-block:: sh

              pip install --user alpaca-prov


    .. tab:: Development version

        If you have `Git <https://git-scm.com/>`_ installed on your system,
        it is also possible to install the development version of Alpaca.

        1. Before installing the development version, you may need to uninstall
           the previously installed version of Alpaca:

           .. code-block:: sh

              pip uninstall alpaca-prov

        2. Clone the repository install the local version:

           .. code-block:: sh

              git clone git://github.com/INM-6/alpaca.git
              cd alpaca
              pip install -e .


.. _visualization:

External tools for provenance visualization
-------------------------------------------

In order to visualize the provenance data saved using Alpaca, a graph
visualization software is needed. Currently, any application that supports the
GEXF or GraphML formats can be used.

It is recommended to use `Gephi <https://gephi.org/>`_:

1. Download the Gephi installation bundle for your system
   `here <https://gephi.org/users/download/>`__.

2. Follow the instructions for your system
   `here <https://gephi.org/users/install/>`__.


Dependencies
------------

Alpaca relies on the following packages (automatically installed when you
run ``pip install alpaca-prov``):

    * `rdflib <https://pypi.org/project/rdflib/>`_ - working with RDF
    * `networkx <https://pypi.org/project/networkx/>`_ - representation and manipulation of graphs in Python
    * `numpy <https://pypi.org/project/numpy/>`_ - fast arrays for scientific computing
    * `joblib <https://pypi.org/project/joblib/>`_ - tools for pipelining in Python, including hashing
    * `dill <https://pypi.org/project/dill/>`_ - extension to Python's pickle module for serializing and de-serializing objects
