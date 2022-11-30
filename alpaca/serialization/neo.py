"""
Module to handle the serialization of Neo objects.

As Neo provides a specific data model for electrophysiology data, some
attributes need special handling. The key component is the annotation
dictionary, that cannot be stored as a standard Python attribute as the
information would not be accessible. A special property `hasAnnotation` is
used for that case.

A special converter for attribute values is also provided, so that they can
be properly serialized to strings.
"""

from alpaca.ontology import ALPACA


__all__ = ['_neo_to_prov', '_neo_object_metadata']


NEO_COLLECTIONS = ('segments', 'events', 'analogsignals',
                   'spiketrains', 'channel_indexes', 'block',
                   'segment', 'epochs', 'parent', '_items', 'waveforms')

DISPLAYED_ATTRIBUTES = ('t_start', 't_stop', 'shape', 'dtype',
                        'name', 'description', 'nix_name')


def _neo_to_prov(value, displayed_attributes=DISPLAYED_ATTRIBUTES):
    # For Neo objects, we create a lightweight representation as a string, to
    # avoid dumping all the information such as SpikeTrain timestamps and
    # Event times as the usual Neo string representation. `value` is a Neo
    # object, and `displayed_attributes` is a list with the Neo object
    # attributes to be displayed in the result string.

    from alpaca.serialization.converters import _ensure_type

    type_information = type(value)
    neo_class = f"{type_information.__module__}.{type_information.__name__}"

    repr = f"{neo_class}("

    counter = 0

    for attribute in displayed_attributes:
        if hasattr(value, attribute):
            if counter > 0:
                repr += ", "

            attr_value = getattr(value, attribute)
            repr += f"{attribute}={_ensure_type(attr_value)}"

            counter += 1

    repr += ")"
    return repr


def _neo_object_metadata(graph, uri, metadata):
    # Adds metadata of a Neo object to an entity in the RDF graph `graph`.
    # `uri` is the identifier of the object in the graph, and `metadata` is
    # the dictionary of object metadata captured by Alpaca.

    from alpaca.serialization.converters import _ensure_type
    from alpaca.serialization.prov import _add_name_value_pair

    for name, value in metadata.items():

        if name in NEO_COLLECTIONS:
            # A collection or a container...

            if isinstance(value, list):
                # This is a collection of Neo objects. Extract the
                # readable name of each Neo object in the list. They will be
                # enclosed in brackets [] as the value stored in the
                # serialized file.
                attr_value = "["
                counter = 0
                for item in value:
                    if counter > 0:
                        attr_value += ", "
                    attr_value += _neo_to_prov(item)
                    counter += 1
                attr_value += "]"
            else:
                # This is a container Neo object. Just get the readable
                # name of the object
                attr_value = _neo_to_prov(value)

            # Add the attribute relationship to the object Entity
            _add_name_value_pair(graph,
                                 uri=uri,
                                 predicate=ALPACA.hasAttribute,
                                 name=name,
                                 value=attr_value)

        elif name in ('annotations', 'array_annotations') and \
                isinstance(value, dict):
            # Handle the annotations in Neo objects

            for annotation, annotation_value in value.items():
                # Make sure that types such as list and Quantity are
                # handled
                annotation_value = _ensure_type(annotation_value)

                # Add the annotation relationship
                _add_name_value_pair(graph,
                                     uri=uri,
                                     predicate=ALPACA.hasAnnotation,
                                     name=annotation,
                                     value=annotation_value)

        else:
            # Other attributes, just add them
            value = _ensure_type(value)

            # Add attribute relationship
            _add_name_value_pair(graph,
                                 uri=uri,
                                 predicate=ALPACA.hasAttribute,
                                 name=name,
                                 value=value)
