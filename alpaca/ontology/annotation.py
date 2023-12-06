"""
Alpaca has functionality to embed semantic information provided by ontologies
by reading annotations that were inserted into Python objects. The annotations
are used by the :class:`alpaca.AlpacaProvDocument` class when serializing the
provenance information as RDF. The annotations will be inserted as additional
`rdf:type` triples alongside the classes already defined by the Alpaca PROV
model.

It expects that the Python object has a dictionary stored as the special
`__ontology__` attribute. All the specific annotations for the Python object
are contained in this dictionary. The annotations are URIs of the
relevant ontology classes that represent the Python object (e.g., a function)
or one of its elements (e.g., the parameters of the function). If providing a
full URI (i.e., without an ontology namespace as prefix - CURIEs), the URI
must start with `<` and end with `>` (e.g.,
`<http://example.org/ontology#Class>`). CURIEs are allowed in the form
`ontology:Class`.

Currently, annotations for two main Python objects are supported: functions
(intended for a Python function object) and data objects (intended for
instances of objects instantiated from a Python class). Specific keys in the
`__ontology__` dictionary will define the main URI describing either the
function or the data object:

* 'function' : str or list of str
   A URI to the ontology class representing the Python function. Multiple URIs
   can be passed as a list, if the function is represented by multiple classes.
* 'data_object' : str or list of str
   A URI to the ontology class representing the Python data object. Multiple
   URIs can be passed as a list, if the object is represented by multiple
   classes.

Additional annotations can be stored depending on whether a function or data
object is being annotated.

For functions, the additional items that can be stored in the `__ontology__`
dictionary are:

* 'arguments' : dict
   A dictionary where the keys are argument names (cf. the function
   declaration in the `def` statement) and the values are the URI(s)
   to the ontology class(es) representing the argument.
* 'returns' : dict
   A dictionary where the keys are function outputs, and the values define the
   URI(s) to the ontology class(es) representing each output identified by a
   key.
   The keys in the `returns` dictionary can have three possible values:
   1. a string with one output name (if this is the name of an argument, cf.
   the function declaration in the `def` statement), which assumes that a
   function uses one of the arguments as output, or
   2. an integer corresponding to the order of the output (as defined by the
   function `return` statements), or
   3. a string of `*`s. In this case, the function returns a container (e.g.,
   a list, or list of lists), and the number of `*`s defines the depth
   within the container whose elements are defined by the ontology class in
   the value. For instance, if the function returns a list of lists
   `[[obj1, obj2], [obj3, obj4], ...]`, the objects are at the third level. If
   each element `objX` is represented by an ontology class defined by `<URI>`,
   one can annotate the elements with a key `'***'` and value `'<URI>'`. An
   annotation with key `'*'` would be used to annotate the main list returned,
   and the key `'**'` would be used to annotate each inner list inside the
   main list (e.g., `[obj1, obj2]` or `[obj3, obj4]`). This is useful for using
   ontologies that define concepts that represent groups of elements.

For data objects, the additional items that can be stored in the `__ontology__`
dictionary are:

* 'attributes' : dict
   A dictionary where the keys are object attribute names and the values are
   the URI(s) to the ontology class(es) representing the attribute.
* 'annotations' : dict
   A dictionary where the keys are annotation names and the values are the
   URI(s) to the ontology class(es) representing the annotation. Annotations
   are key-pair values specified in dictionaries stored as one attribute of the
   object (e.g., `obj.annotations`).

Finally, the ontology annotations can be defined using namespaces so that the
URIs are shortened (CURIEs). Namespaces are defined for both functions and
data objects using the `namespaces` key in the `__ontology__` dictionary:

* 'namespaces' : dict
   A dictionary where the keys are the names used as prefixes in the
   annotations in `__ontology__` and the values are the prefix URIs to be
   expanded to get the final URI. For example, for an ontology with URIs with
   prefix `http://example.org/ontology#`, such as
   `<http://example.org/ontology#ClassA>` and
   `<http://example.org/ontology#ClassB>` a namespace
   `'ontology'="http://example.org/ontology#"` can be defined such as the
   classes can be referred to as `ontology:ClassA` and `ontology:ClassB`.


Examples
--------

Consider the Python function `process` that takes an input `data`, is
controlled by a parameter `param`, and returns a tuple of two elements:

>>> def process(data, param):
>>>     ...  # process `data` into `output1` and `output2` using `param`
>>>     return output1, output2

To use an ontology defined by the base URI `<http://my-ontology#>` to annotate
the `process` Python function, whose concept is defined by
`<http://my-ontology#ProcessClass>`, and where `data` is represented by
`<http://my-ontology#DataClass>`, `param` by
`<http://my-ontology#ParameterClass>` and the second return element (`output2`)
needs to be annotated with class `<http://my-ontology#ProcessOutputClass>`,
the following dictionary could be inserted into the `process` function object:

>>> process.__ontology__ = {
>>>     'function': "my_ontology:ProcessClass",
>>>     'arguments': {'data': "my_ontology:DataClass",
>>>                   'param': "my_ontology:ParameterClass"},
>>>     'returns': {1: "my_ontology:ProcessOutputClass"},
>>>     'namespaces': {"my_ontology": "http://my-ontology#"}
>>> }

For a Python function `process_container`, represented by
`<http://my-ontology#ProcessContainerClass>` that takes the same inputs but
returns a list of objects that need to be annotated with the ontology class
`<http://my-ontology#ProcessOutputElementClass>`, the following dictionary
could be used:

>>> def process_container(data, param):
>>>     ...  # process `data` into several outputs grouped as a list `output`
>>> return output    # [obj1, obj2, ...]

>>> process_container.__ontology__ = {
>>>     'function': "my_ontology:ProcessContainerClass",
>>>     'arguments': {'data': "my_ontology:DataClass",
>>>                   'param': "my_ontology:ParameterClass"},
>>>     'returns': {'**': "my_ontology:ProcessOutputElementClass"},
>>>     'namespaces': {"my_ontology": "http://my-ontology#"}
>>> }

"""

import rdflib
from copy import deepcopy


# Two types of Python objects can be annotated: functions or data objects.
# For each, specific additional information can also be annotated (e.g.,
# the parameters of a function). This dictionary defines which can be defined
# for each entity, and the strings that are used as keys in the `__ontology__`
# dictionary.
VALID_INFORMATION = {
    'data_object': {'namespaces', 'attributes', 'annotations'},
    'function': {'namespaces', 'arguments', 'returns'}
}
VALID_OBJECTS = set(VALID_INFORMATION.keys())


# Global dictionary to store ontology information during the capture.
# This is used later for the serialization.
ONTOLOGY_INFORMATION = {}


class _OntologyInformation(object):
    """
    Class used to parse information from the `__ontology__` annotation
    dictionary from Python functions or data objects.

    This class provides easy access to the definitions when serializing the
    provenance information with extended ontology annotations. It also manages
    namespaces across different objects and functions, such that no ambiguities
    or multiple definitions are introduced, and the full URIs can be retrieved.

    This class is used internally by Alpaca when serializing the provenance
    as RDF.

    Parameters
    ----------
    obj : object
        Python function or data object with an attribute named `__ontology__`
        that stores a dictionary with specific ontology annotations.
    """

    namespaces = {}

    @classmethod
    def add_namespace(cls, name, uri):
        if name in cls.namespaces:
            if cls.namespaces[name] != uri:
                raise ValueError("Attempting to redefine an existing "
                                 "namespace. This is not allowed as other "
                                 "terms expect a different URI.")
        else:
            cls.namespaces[name] = rdflib.Namespace(uri)

    @classmethod
    def bind_namespaces(cls, namespace_manager):
        for name, namespace in cls.namespaces.items():
            namespace_manager.bind(name, namespace)

    @staticmethod
    def get_ontology_information(obj):
        if hasattr(obj, "__ontology__"):
            return getattr(obj, "__ontology__")
        elif (hasattr(obj, "__wrapped__") and
              hasattr(obj.__wrapped__, "__ontology__")):
            return getattr(obj.__wrapped__, "__ontology__")
        return None

    def __init__(self, obj):

        ontology_info = self.get_ontology_information(obj)
        if ontology_info:
            # An ontology annotation with semantic information is present
            # Store each element inside this object

            for information_type, information in ontology_info.items():
                if information_type in VALID_OBJECTS:
                    # Function or data object URI
                    setattr(self, information_type, information)
                elif information_type == "namespaces":
                    # Add all namespaces, checking for inconsistencies
                    for prefix, uri in information.items():
                        self.add_namespace(prefix, uri)
                else:
                    # Add additional information on the function or data
                    # object
                    setattr(self, information_type, deepcopy(information))

    def has_information(self, information_type):
        return hasattr(self, information_type)

    def get_container_returns(self):
        returns = getattr(self, 'returns', None)
        if returns:
            return [key for key in returns.keys() if isinstance(key, str) and
                    key == '*' * len(key)]
        return None

    def get_uri(self, information_type, element=None):
        if information_type in VALID_OBJECTS:
            # Information on 'function' and 'data_object' are strings or
            # lists, stored directly as attributes
            information_value = getattr(self, information_type)
        else:
            # Specific information of 'function' and 'data_object' are
            # stored in dictionaries (e.g., 'attributes', 'parameters'...)
            information = getattr(self, information_type, None)

            if information is None:
                # No information available
                return None

            # If annotating all elements (e.g., multiple returns in a
            # container). The actual element will not be present, but
            # there will be an entry identified by '*'.
            information_value = information.get(element, None)
            if not information_value:
                return None

        if not isinstance(information_value, list):
            information_value = [information_value]

        # Process URI(s) to get `rdflib.URIRef` elements, resolving any
        # namespace.
        uris = []
        for uri in information_value:
            if (uri[0], uri[-1]) == ("<", ">"):
                # This is a full URI
                uris.append(rdflib.URIRef(uri[1:-1]))
            else:
                # If not full URIs, information must be CURIEs.
                # Get the `URIRef` from the namespace.
                prefix, value = uri.split(":")
                uris.append(self.namespaces[prefix][value])

        if len(uris) == 1:
            # Return annotation with a single URI directly
            return uris[0]
        return uris

    def __repr__(self):
        repr_str = "OntologyInformation("
        information = []
        for obj_type in VALID_OBJECTS:
            if self.has_information(obj_type):
                information.append(f"{obj_type}='{getattr(self, obj_type)}'")
                for specific_information in \
                        sorted(VALID_INFORMATION[obj_type]):
                    if self.has_information(specific_information):
                        specific_info = getattr(self, specific_information)
                        info_str = str(specific_info) \
                            if not isinstance(specific_info, str) else \
                            f"'{specific_info}'"
                        information.append(
                            f"{specific_information}={info_str}")
                repr_str = f"{repr_str}{', '.join(information)})"
        return repr_str
