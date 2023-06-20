"""
This module implements a class to read annotations inserted into Python
objects. It expects a dictionary as the `__ontology__` attribute.

The items that can be stored in the dictionary are:

* 'function' : str
   An IRI to the ontology class representing the function.
* 'package': str
   An IRI to the individual representing the package information.
* 'data_object' : str
   An IRI to the ontology class representing the Python data object.
* 'arguments' : dict
   A dictionary where the keys are parameter names and the values are the IRI
   to the ontology class representing the parameter.
* 'returns' : dict
   A dictionary where the keys are output names (or the output order when a
   tuple is returned) and the values are the IRI to the ontology class
   representing it.
* 'attributes' : dict
   A dictionary where the keys are object attribute names and the values are
   the IRI to the ontology class representing the attribute.
* 'annotations' : dict
   A dictinoary where the keys are annotation names and the values are the
   IRI to the ontology class representing the annotation.
* 'namespaces' : dict
   A dictionary where the keys are the names used as prefixes and the values
   are the prefixed IRIs to be expanded.

The decorator `annotate_ontology` is provided to insert ontology information
into functions.

"""
import rdflib
from copy import deepcopy
from functools import partial
from itertools import chain


# Two types of entities can be annotated: functions or data objects.
# For each, specific additional information can also be annotated (e.g.,
# the parameters of a function). This dictionary defines which can be defined
# for each entity, and the strings that are used as keys in the `__ontology__`
# dictionary.
VALID_INFORMATION = {
    'data_object': ('namespaces', 'attributes', 'annotations'),
    'function': ('namespaces', 'arguments', 'returns', 'package')
}
VALID_OBJECTS = set(VALID_INFORMATION.keys())
VALID_ANNOTATIONS = set(VALID_INFORMATION.values())


# Global dictionary to store ontology information during the capture.
# This is used later for the serialization.
ONTOLOGY_INFORMATION = {}


class OntologyInformation(object):

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
    def has_ontology(obj):
        return hasattr(obj, "__ontology__")

    def __init__(self, obj):

        if self.has_ontology(obj):
            # An ontology annotation with semantic information is present
            # Store each element inside this object

            for information_type, information in obj.__ontology__.items():
                if information_type in VALID_OBJECTS:
                    setattr(self, information_type, information)
                elif information_type == "namespaces":
                    for prefix, iri in information.items():
                        self.add_namespace(prefix, iri)
                else:
                    setattr(self, information_type, deepcopy(information))

    def has_information(self, information_type):
        return hasattr(self, information_type)

    def get_iri(self, information_type, element=None):
        if information_type in VALID_OBJECTS:
            # Information on 'function', 'data_object' and 'package' are
            # strings, stored directly as attributes
            information_value = getattr(self, information_type)
        else:
            # Specific information of 'function' and 'data_object' are
            # stored in dictionaries (e.g., 'attributes', 'parameters'...)
            information = getattr(self, information_type, None)
            if information is None or element not in information:
                return None
            information_value = information[element]

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
                for specific_information in VALID_INFORMATION[obj_type]:
                    if self.has_information(specific_information):
                        specific_info = getattr(self, specific_information)
                        info_str = str(specific_info) \
                            if not isinstance(specific_info, str) else \
                            f"'{specific_info}'"
                        information.append(
                            f"{specific_information}={info_str}")
                repr_str = f"{repr_str}{', '.join(information)})"
        return repr_str


def update_ontology_information(obj, obj_type, obj_iri, namespaces=None,
                                **kwargs):
    """
    Updates the ontology information in an object. This can be a function or
    an object holding data.

    Parameters
    ----------
    obj : object
        Function or data object. It must allow attribute assignment.
    obj_type : {'function', 'data_object'}
        Defines the type of object being annotated. This is used to filter
        additional information that can be annotated using `kwargs`.
    namespaces : dict
        Dictionary where the keys are the prefixes of the namespaces used in
        the annotations, and the values are the IRI representing the namespace.
    kwargs : dict
        Additional information on the object `obj`. The key is the type of
        information, and the values are a dictionary, where the keys identify
        the information and the values are the IRIs of the ontology identifying
        the term.
        This depends on `obj_type`:
        * `'function'`: `arguments`, `returns`, to identify the names of any
          argument present in the function definition, or the returns. In case
          of tuples, the key of the dictionary is an integer with the order of
          the objects returned.
        * `'data_object'`: `attributes`, `annotations`, to identify the names
          of object attributes or annotations (as elements in an `annotations`
          dictionary) respectively.
    """
    if obj_type not in VALID_OBJECTS:
        raise ValueError(f"Invalid object type: {obj_type}")

    obj.__ontology__ = {obj_type: obj_iri}

    if namespaces is not None:
        kwargs['namespaces'] = namespaces

    for information_type, value in kwargs.items():
        if value and information_type in VALID_INFORMATION[obj_type]:
            obj.__ontology__[information_type] = deepcopy(value)

    return obj


def annotate_function_with_ontology(function_iri, **kwargs):

    def wrapped(function):

        if {'attributes', 'annotations'}.intersection(set(kwargs.keys())):
            raise ValueError("Invalid annotations for a function")

        # Dictionary will be passed to `update_ontology_information`
        info = {'obj_type': 'function',
                'obj_iri': function_iri}
        info.update(kwargs)

        # Use original function if wrapped
        if hasattr(function, "__wrapped__"):
            update_ontology_information(function.__wrapped__, **info)
            return function

        return update_ontology_information(function, **info)

    return wrapped
