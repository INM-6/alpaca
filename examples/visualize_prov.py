"""
This script parses provenance data saved by Alpaca in the W3C PROV format,
and exports a graph for visualization using third-party software (e.g. Gephi).
It is supposed to work with the output of `run_basic.py`.

Usage:

    visualize_prov.py [Alpaca_PROV_file] [output_GEXF_file]

This script is the basis for the "Visualize provenance data" page in the
Examples section of the documentation.
"""

import sys
from alpaca import ProvenanceGraph


def main(file_name, output_file):

    # Attributes and annotations that should be displayed in the nodes, if
    # available
    attributes = ['shape', 'dtype', 'name']
    annotations = ['subject_name', 'id', 'channel_id']

    # Load tye PROV document into the graph, and extract the information
    # requested
    prov_graph = ProvenanceGraph(prov_file=file_name,
                                 attributes=attributes,
                                 annotations=annotations)

    # Saves the graph for loading in a visualization software
    prov_graph.save_gexf(output_file)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise ValueError("You must inform the source file")

    main(sys.argv[1], sys.argv[2])
