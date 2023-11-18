"""
This module implements functionality to read semantic annotations using
ontologies that were inserted into Python entities.

It expects that the Python entity has a dictionary stored as the
`__ontology__` attribute. All the specific annotations for the Python entity
are contained in this dictionary.

Currently, two main types of annotation groups are supported: functions
(intended for a Python function) and data objects (intended for a Python
class). Specific keys in the `__ontology__` dictionary will define the
main IRI describing either the function or the data object:

* 'function' : str
   An IRI to the ontology class representing the Python function.
* 'data_object' : str
   An IRI to the ontology class representing the Python data object.

Additional annotations can be stored depending on whether a function or data
object is being annotated.

For functions, the additional items that can be stored in the `__ontology__`
dictionary are:

* 'package': str
   An IRI to the individual representing the package where the function is
   implemented.
* 'arguments' : dict
   A dictionary where the keys are argument names (cf. the function
   declaration in the `def` statement) and the values are the IRI
   to the ontology class representing the argument.
* 'returns' : dict
   A dictionary where the keys are strings with the output names (if defined
   in the function arguments) or integers corresponding to the order of the
   output (as defined by the function returns). The values are the IRI to the
   ontology class representing each output identified by the key.

For data objects, the additional items that can be stored in the `__ontology__`
dictionary are:

* 'attributes' : dict
   A dictionary where the keys are object attribute names and the values are
   the IRI to the ontology class representing the attribute.
* 'annotations' : dict
   A dictionary where the keys are annotation names and the values are the
   IRI to the ontology class representing the annotation. Annotations are
   key-pair values specified in dictionaries stored as one attribute of the
   object (e.g., `obj.annotations`).

Finally, the ontology annotations can be defined using namespaces so that the
IRIs are shortened. Namespaces are defined for both functions and data objects
using the `namespaces` value in the `__ontology__` dictionary:

* 'namespaces' : dict
   A dictionary where the keys are the names used as prefixes in the
   annotations in `__ontology__` and the values are the prefixed IRIs to be
   expanded to get the final IRI.
"""

import rdflib
from copy import deepcopy


# Two types of entities can be annotated: functions or data objects.
# For each, specific additional information can also be annotated (e.g.,
# the parameters of a function). This dictionary defines which can be defined
# for each entity, and the strings that are used as keys in the `__ontology__`
# dictionary.
VALID_INFORMATION = {
    'data_object': {'namespaces', 'attributes', 'annotations'},
    'function': {'namespaces', 'arguments', 'returns', 'package'}
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
    or multiple definitions are introduced, and the full IRIs can be retrieved.

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
    def add_namespace(cls, name, iri):
        if name in cls.namespaces:
            if cls.namespaces[name] != iri:
                raise ValueError("Attempting to redefine an existing "
                                 "namespace. This is not allowed as other "
                                 "terms expect a different IRI.")
        else:
            cls.namespaces[name] = rdflib.Namespace(iri)

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
                    # Function or data object IRI
                    setattr(self, information_type, information)
                elif information_type == "namespaces":
                    # Add all namespaces, checking for inconsistencies
                    for prefix, iri in information.items():
                        self.add_namespace(prefix, iri)
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

    def get_iri(self, information_type, element=None):
        if information_type in VALID_OBJECTS:
            # Information on 'function', 'data_object' and 'package' are
            # strings, stored directly as attributes
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

        if (information_value[0], information_value[-1]) == ("<", ">"):
            # This is an IRI
            return rdflib.URIRef(information_value[1:-1])

        # If not full IRIs, information must be CURIEs. Get the URIRef.
        prefix, value = information_value.split(":")
        return self.namespaces[prefix][value]

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
