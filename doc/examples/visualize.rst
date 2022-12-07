*************************
Visualize provenance data
*************************

The **visualize_prov.py** script shows the basic functionality to generate
a graph file from serialized provenance data.

The script takes a file serialized in one of the RDF formats (e.g. Turtle) and
writes a GEXF file.


Running the script
------------------

The usage is:

.. code-block:: sh

    python visualize_prov.py [path_to_alpaca_PROV_file] [path_to_dest_GEXF_file]


Importing Alpaca and necessary objects
--------------------------------------

We start by importing the **ProvenanceGraph** object:

.. code-block:: python

    from alpaca import ProvenanceGraph


Selecting data to include in the visualization
----------------------------------------------

The captured metadata within the provenance track can be extensive. By default,
Alpaca captures all object attributes and, for some specific packages (e.g.,
Neo), additional information is captured in the form of annotations and array
annotations. You can pass lists of names to Alpace to limit the information
to include in the visualization graph to avoid cluttering.


Attributes
~~~~~~~~~~

Attributes are the usual Python object attributes (e.g. `object.name`). Alpaca
stores attribute values when the data objects are tracked. In the PROV files,
their values are stored with the `hasAttribute` property.

For example, when working with NumPy arrays, it is useful to check the
dimensions of the array (`shape` attribute), and also the data type stored
(`dtype` attribute). To include these attributes, we need a list/tuple like:

.. code-block:: python

    attributes = ['shape', 'dtype', 'name']

Here we also include the value of `name` if any object has it defined (e.g.,
Neo objects).


Annotations
~~~~~~~~~~~

Annotations are values stored inside a dictionary accessible by the
`annotations` or `array_annotations` attributes of the Python object.
These values are stored by Alpaca in PROV files in the form of
`hasAnnotation` properties. Array annotations are a special type of annotation.
For a Python object that is itself an array, with multiple elements, each
value in an array annotation will refer to the respective element in the
Python object.

For example, the `neo.Block` object may have a custom field called
`subject_name` to identify the name of the subject used in an
electrophysiology recording. For a `neo.Block` loaded into variable `block`,
this would be stored inside `block.annotations`. The dictionary would be
`{'subject_name': 'monkey_L'}`.

Additionally, for a `neo.SpikeTrain`, different annotations could be present,
such as `id` for the neuron identification, and `channel_id` indicating the channel
number from which the signal used to extract the neuron was obtained.
As there are multiple spike times stored in the `neo.SpikeTrain` object, an
array annotation will contain metadata referring to each individual spike.

To include the `subject_name`, `id` and `channel_id` annotation values in the 
visualization, we need a list/tuple like:

.. code-block:: python

    annotations = ['subject_name', 'id', 'channel_id']


Generating the visualization graph
----------------------------------

We can generate the visualization graph by passing the file name and
selected attributes/annotations to the **ProvenanceGraph** object:

.. code-block:: python

    prov_graph = ProvenanceGraph(prov_file=file_name,
                                 attributes=attributes,
                                 annotations=annotations)

Saving the graph file
---------------------

To save the graph as GEXF:

.. code-block:: python

    prov_graph.save_gexf(output_file)

Now, `output_file` is a GEXF file that can be read by Gephi to visualize a
graph with the provenance history, the object details, and function parameters.
For the output of the simple example (**run_basic.ttl**), you will have a file
called **run_basic.gexf**.
