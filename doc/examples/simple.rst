**************
Simple example
**************

The **run_basic.py** script shows the basic functionality of Alpaca.
The script takes one of the Reach2Grasp datasets as argument. The provenance
information will be saved as **run_basic.ttl** in the RDF Turtle format.
You can modify it to export according to other serialization formats.

Running the script
------------------

Usage is:

.. code-block:: sh

    python run_basic.py [path_to_dataset]

This script parses the arguments and call the **main** function with the
file name as parameter. The main code to be tracked is within the **main**
function.


Importing Alpaca and necessary functions
----------------------------------------

You start by importing the **Provenance** decorator and the interface
functions:

.. code-block:: python

    from alpaca import Provenance, activate, save_provenance

You can also import some utility functions to facilitate generating file
names:

.. code-block:: python

    from alpaca.utils import get_file_name


Applying the decorator
----------------------

User-defined functions
~~~~~~~~~~~~~~~~~~~~~~

You can use the syntactic sugar **@** to apply the decorator in the functions
you defined in your own script:

.. code-block:: python

    @Provenance(inputs=['isi_times'])
    def isi_histogram(isi_times, bin_size=2*pq.ms, max_time=500*pq.ms):

The `inputs` parameter is mandatory. You should list the names of the arguments
that are inputs to the function. If a function does not take inputs, you should
pass an empty list. In the example above, `bin_size` and `max_time` are not
inputs, but parameters of the function, and will influence how `isi_histogram`
is producing its output.

If a function reads one or more files (source defined by arguments), you can
set this using the `file_input` parameter:

.. code-block:: python

    @Provenance(inputs=[], file_input=['session_filename'])
    def load_data(session_filename):

If a function writes one or more files (destination defined by arguments), you
can set this using the `file_output` parameter:

.. code-block:: python

    @Provenance(inputs=['counts', 'edges'], file_output=['plot_file'])
    def plot_isi_histogram(plot_file, counts, edges, title=None):


Imported functions
~~~~~~~~~~~~~~~~~~

You can also wrap any imported function in the decorator:

.. code-block:: python

    from elephant.statistics import isi
    isi = Provenance(inputs=['spiketrain'])(isi)

The use of the decorator parameters is the same as for the user-defined
functions (`inputs`, `file_input`, `file_output`).


Activating provenance tracking
------------------------------

At the beginning of your code block, you call the **activate** function:

.. code-block:: python

    def main(session_filename):
        activate()

        ...

Saving captured provenance at the end of the script
---------------------------------------------------

After all your functions are called, you can serialize the history easily
using **save_provenance**:

.. code-block:: python

    save_provenance(prov_file)

An utility function allows to easily provide a name for your script execution
provenance:

.. code-block:: python

    prov_file = get_file_name(__file__, extension='ttl')


After executing this script, you will have the output file **isi_plot.png**
together with the **run_basic.ttl** file with the serialized provenance.
