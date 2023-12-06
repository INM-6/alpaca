"""
Module to handle the serialization of Neo objects. This defines plugin
functions that are used by Alpaca when serializing information from Neo
objects in the captured provenance.

As Neo provides a specific data model for electrophysiology data, some
attributes need special handling. The key component is the `annotations`
dictionary, that cannot be stored as a standard Python attribute as the
information would not be accessible. A special property `hasAnnotation` is
used for those cases, where each key-value pair in the annotations dictionary
is identified as object metadata.

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

    attr_repr = []
    for attribute in displayed_attributes:
        if hasattr(value, attribute):
            attr_value = getattr(value, attribute)
            attr_repr.append(f"{attribute}={_ensure_type(attr_value)}")

    neo_repr = f"{neo_class}({', '.join(attr_repr)})"
    return neo_repr


def _neo_object_metadata(graph, uri, metadata):
    # Adds metadata of a Neo object to an entity in the RDF graph `graph`.
    # `uri` is the identifier of the object in the graph, and `metadata` is
    # the dictionary of object metadata captured by Alpaca.
    # Returns a dictionary of attribute/annotation names with blank node
    # URIs, that are used later for inserting semantic information if
    # ontology annotations are defined.

    from alpaca.serialization.converters import _ensure_type
    from alpaca.serialization.prov import _add_name_value_pair

    metadata_nodes = {'attributes': {}, 'annotations': {}}

    for name, value in metadata.items():

        if name in NEO_COLLECTIONS:
            # A collection or a container...

            if isinstance(value, list):
                # This is a collection of Neo objects. Extract the
                # readable name of each Neo object in the list. They will be
                # enclosed in brackets [] as the value stored in the
                # serialized file.
                attr_values = []
                for item in value:
                    attr_values.append(_neo_to_prov(item))
                attr_value = f"[{', '.join(attr_values)}]"
            else:
                # This is a container Neo object. Just get the readable
                # name of the object
                attr_value = _neo_to_prov(value)

            # Add the attribute relationship to the object Entity
            blank_node = _add_name_value_pair(graph,
                                              uri=uri,
                                              predicate=ALPACA.hasAttribute,
                                              name=name,
                                              value=attr_value)
            metadata_nodes['attributes'][name] = blank_node

        elif name in ('annotations', 'array_annotations') and \
                isinstance(value, dict):
            # Handle the annotations in Neo objects

            for annotation, annotation_value in value.items():
                # Make sure that types such as list and Quantity are
                # handled
                annotation_value = _ensure_type(annotation_value)

                # Add the annotation relationship
                blank_node = _add_name_value_pair(graph,
                                            uri=uri,
                                            predicate=ALPACA.hasAnnotation,
                                            name=annotation,
                                            value=annotation_value)
                metadata_nodes['annotations'][name] = blank_node

        else:
            # Other attributes, just add them
            value = _ensure_type(value)

            # Add attribute relationship
            blank_node = _add_name_value_pair(graph,
                                              uri=uri,
                                              predicate=ALPACA.hasAttribute,
                                              name=name,
                                              value=value)
            metadata_nodes['attributes'][name] = blank_node

    return metadata_nodes
