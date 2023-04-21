"""
This module implements a class to read annotations inserted into Python
objects. It expects a dictionary as the `__ontology__` attribute.

The items that can be stored in the dictionary are:

* 'function' : str
   An IRI to the ontology class representing the function.
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
   A dictionary where the keys are the name used as prefix and the values are
   the prefixed IRI to be expanded.

The decorator `annotate_ontology` is provide to insert ontology information
into functions.

"""
import rdflib
from copy import deepcopy
from functools import partial


VALID_INFORMATION = {
    'data_object': ('namespaces', 'attributes', 'annotations'),
    'function': ('namespaces', 'arguments', 'returns')
}
VALID_OBJECTS = list(VALID_INFORMATION.keys())


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
            information_value = getattr(self, information_type)
        else:
            information = getattr(self, information_type)
            if element not in information:
                return None
            information_value = information[element]

        if (information_value[0], information_value[-1]) == ("<", ">"):
            # This is an IRI
            return rdflib.URIRef(information_value[1:-1])

        # If not full IRIs, information must be CURIEs
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
                        information.append(
                            f"{specific_information}="
                            f"{getattr(self, specific_information)}")
                repr_str = f"{repr_str}{', '.join(information)})"
        return repr_str


# Annotation decorator


def update_ontology_information(obj, obj_type, obj_iri, **kwargs):
    if obj_type not in VALID_OBJECTS:
        raise ValueError(f"Invalid object type: {obj_type}")

    obj.__ontology__ = {obj_type: obj_iri}

    for information_type, value in kwargs.items():
        if value and information_type in VALID_INFORMATION[obj_type]:
            obj.__ontology__[information_type] = deepcopy(value)

    return obj


def annotate_ontology(function_iri, **kwargs):

    def decorator(function):

        if {'attributes', 'annotations'}.intersection(set(kwargs.keys())):
            raise ValueError("Invalid annotations for a function")

        info = {'obj_type': 'function',
                'obj_iri': function_iri}
        info.update(kwargs)

        # Use original function if wrapped
        if hasattr(function, "__wrapped__"):
            update_ontology_information(function.__wrapped__, **info)
            return function

        return update_ontology_information(function, **info)

    return decorator


annotate_eao = partial(annotate_ontology,
                       namespaces={"eao": "http://eao.ontology/owl#"})

@annotate_eao("eao:add", arguments={"a": "eao:operand", "b": "eao:operand"},
              returns={0: "eao:result"})
def test(a, b):
    return a + b


@annotate_eao("eao:add2")
def test2(a, b):
    return a + b + b


if __name__ == "__main__":

    for fn in (test, test2):
        print(fn(1, 2))
        print(fn.__ontology__)
        print(fn.__qualname__, fn.__name__)

        annotation = OntologyInformation(fn)
        print(annotation)
        print(OntologyInformation.namespaces)
