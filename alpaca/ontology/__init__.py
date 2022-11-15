"""
This module contains the OWL ontology based on the PROV-O model from W3C, that
is used to represent provenance information captured by Alpaca.
An RDFLib namespace is provided, to be used in other modules.
"""

from rdflib import Graph, Namespace
import pathlib


ONTOLOGY_SOURCE = pathlib.Path(__file__).with_name("alpaca.owl")


def get_alpaca_namespace():
    g = Graph()
    g.parse(ONTOLOGY_SOURCE, format='ttl')
    for prefix, uri in g.namespaces():
        if prefix == "":
            return Namespace(uri)
    raise ValueError("Could not get Alpaca ontology namespace.")


# Namespace object to be used with RDFLib graphs
ALPACA = get_alpaca_namespace()
