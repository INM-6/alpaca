*****************************
Preparing to run the examples
*****************************

Downloading the datasets
------------------------

A publicly available experimental dataset (Brochier et al. (2018) Scientific Data 5:
180055; `https://doi.org/10.1038/sdata.2018.55 <https://doi.org/10.1038/sdata.2018.55>`_)
is used in the examples, available at
`https://doi.gin.g-node.org/10.12751/g-node.f83565 <https://doi.gin.g-node.org/10.12751/g-node.f83565>`_.

The dataset that is used in the examples is **l101210-001.nix**, and must be downloaded
to your computer. It can be directly accessed at `the GIN repository <https://gin.g-node.org/INT/multielectrode_grasp/raw/to_nix/datasets_nix/l101210-001.nix>`_.


Running the examples
--------------------

A suitable environment can be built using `conda <http://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html>`_
with the **environment.yaml** file located in the **examples** folder.

.. code-block:: sh

    conda env create -f environment.yaml


If configuring your own environment, the following additional packages are
required (Python 3.8+):

* Neo (`https://neuralensemble.org/neo <https://neuralensemble.org/neo>`_)
* Elephant (`https://python-elephant.org <https://python-elephant.org>`_)
* nixio (`https://pypi.org/project/nixio/ <https://pypi.org/project/nixio/>`_)
* matplotlib (`https://matplotlib.org/ <https://matplotlib.org/>`_)

