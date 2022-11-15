*****************************
Preparing to run the examples
*****************************

Downloading the datasets
------------------------

The Reach2Grasp experimental dataset [Brochier et al. (2018) Scientific Data 5:
180055; `https://doi.org/10.1038/sdata.2018.55 <https://doi.org/10.1038/sdata.2018.55>`_]
is used in the examples. The repository must be downloaded to your local
computer. Please, follow the instructions on:

`https://doi.gin.g-node.org/10.12751/g-node.f83565 <https://doi.gin.g-node.org/10.12751/g-node.f83565>`_

At this website, you can either download a large archive (.zip) or access
the GIN repository where the data is hosted. In the latter case, instructions
to download the data and code using the *gin* client are provided.


Running the examples
--------------------

To use the experimental datasets to run the examples, you must first add the
location of the *reachgraspio.py* file in your local computer to the
*PYTHONPATH* environmental variable. This is located in the folder where you
downloaded the Reach2Grasp dataset, in the subfolder *code/reachgraspio*.

Assuming that the Reach2Grasp repository was downloaded to
*/home/user/multielectrode_grasp*, the following will add it to the
*PYTHONPATH* environmental variable:

.. code-block:: sh

    export PYTHONPATH="$PYTHONPATH:/home/user/multielectrode_grasp/code/reachgraspio"


A suitable environment can be built using `conda <http://docs.conda.io/projects/conda/en/latest/user-guide/install/index.html>`_
with the *environment.yaml* file located in the *examples* subfolder.

If configuring your own environment, the following additional packages are
required (Python 3.8+):

* Neo 0.9.0 (`https://neuralensemble.org/neo <https://neuralensemble.org/neo>`_)
* Elephant 0.10.0 (`https://python-elephant.org <https://python-elephant.org>`_)
* odML (`https://g-node.github.io/python-odml <https://g-node.github.io/python-odml>`_)
