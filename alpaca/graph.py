import re

from prov.model import *
from prov.graph import prov_to_graph
import networkx as nx

from alpaca.serialization import (ProvenanceDocument, NID_ALPACA, NSS_FUNCTION,
                                  NSS_FILE, NSS_DATA, NSS_SCRIPT,
                                  NSS_PARAMETER, NSS_ATTRIBUTE, NSS_ANNOTATION,
                                  NSS_CONTAINER, ALL_NSS, NAMESPACES)
from alpaca.utils.files import _get_prov_file_format


# Utility functions for graph conversion

def _find_namespace(uri):
    for ns in NAMESPACES:
        parts = uri.split(ns.uri)
        if len(parts) > 1:
            return ns.prefix, parts[1]
    return None


def _get_id(uri):
    node_id = str(uri)
    namespace = _find_namespace(node_id)
    if namespace:
        return ":".join(namespace)
    return node_id


def _add_attribute(data, attr_name, attr_type, attr_value, strip_namespace):
    if not strip_namespace:
        attr_name = f"{attr_type}:{attr_name}"

    if attr_name in data:
        raise ValueError(
            "Duplicate property values. Make sure to include the namespaces!")
    data[attr_name] = attr_value


def _get_data(node, node_id, annotations=None, attributes=None,
              array_annotations=None, strip_namespace=True):
    filter_map = defaultdict(list)

    # Array annotations is a special attribute that stores a dictionary
    # We will retrieve it as an ordinary attribute value, and then
    # process later
    if array_annotations:
        attributes = attributes + tuple(array_annotations.keys())

    filter_map.update(
        {NSS_ANNOTATION: annotations, NSS_ATTRIBUTE: attributes})

    data = {"gephi_interval": []}
    namespace, local_part = node_id.split(":", 1)
    data['type'] = "activity" if namespace == NSS_FUNCTION else namespace

    info = local_part.split(":")
    data['data_hash'] = info[-1]
    if namespace == NSS_FILE:
        data['label'] = "File"
        data['hash_type'] = info[-2]
    elif namespace == NSS_DATA:
        data['label'] = info[-2].split(".")[-1]
        data['Python_name'] = info[-2]

    for attr in node.attributes:
        attr_type = str(attr[0].namespace.prefix)
        attr_name = attr[0].localpart
        attr_value = attr[1]

        if annotations or attributes or array_annotations:
            if attr_name in filter_map[attr_type]:
                if attr_name in array_annotations:
                    # Extract the relevant keys from the array annotations string
                    for annotation in array_annotations[attr_name]:
                        search_annotation = re.compile(
                            fr"'({annotation})':\s([\w\s()\/\-.*\[\]'\,=<>]+)(,\s'.+':|,*\}})")

                        match = search_annotation.search(attr_value)

                        if match:
                            if match.group(1) == annotation:
                                value = str(match.group(2))
                                value = re.sub(r"\s+", " ", value)
                            else:
                                value = "<could not fetch annotation value>"

                            _add_attribute(data, annotation, attr_type,
                                           value, strip_namespace)

                else:
                    _add_attribute(data, attr_name, attr_type, attr_value,
                                   strip_namespace)

        if namespace == NSS_FILE and attr_type in (
                "rdfs", "prov") and attr_name == "label":
            data["File_path"] = attr_value

    return data


def _add_gephi_interval(data, order):
    if not "gephi_interval" in data:
        data["gephi_interval"] = []
    data["gephi_interval"].append((order, order))


def _get_function_call_node(u_id, v_id, relation,
                            use_name_in_parameter=True):
    node_id = v_id if isinstance(relation, ProvUsage) else u_id

    data = {
        "Python_name": node_id.split(":")[-1],
        "type": NSS_FUNCTION
    }
    data["label"] = data["Python_name"].split(".")[-1]

    for attr in relation.attributes:
        attr_type = str(attr[0].namespace.prefix)
        attr_name = attr[0].localpart
        attr_value = attr[1]

        if attr_type == "prov" and attr_name == "value":
            data["execution_order"] = attr_value
        elif attr_type == NSS_PARAMETER:
            prefix = attr_type if not use_name_in_parameter else data[
                "label"]
            data[f"{prefix}:{attr_name}"] = attr_value

    _add_gephi_interval(data, data["execution_order"])
    node_hash = hash((node_id, data["execution_order"]))

    return node_hash, data


def _get_membership_relation(relation, graph):
    # Retrieve the relevant parameter (index/slice, attribute)
    # The entity that is inside the collection has an attribute
    # with the namespace `container:`, with the index/slice or
    # attribute name information

    member = None
    for attr in relation.attributes:
        if str(attr[0]) == "prov:entity":
            member = attr[1].uri

    for node in graph.nodes:
        if node.identifier.uri == member:
            # ProvEntity object of the collection's member
            for attr in node.attributes:
                container_attribute = str(attr[0])
                if container_attribute.startswith(f"{NSS_CONTAINER}:"):
                    # This is the membership ProvEntity attribute
                    # Get the attribute name or index/slice value
                    member_type = container_attribute.split(":")[-1]
                    if member_type == "attribute":
                        return f".{attr[1]}"
                    else:
                        return f"[{attr[1]}]"


# Main graph class

class ProvenanceGraph:
    """
    Directed Acyclic Graph representing the provenance history stored in a
    W3C PROV file.

    Parameters
    ----------
    prov_file : str or Path-like
        Source file with provenance data in W3C PROV format.
    annotations : tuple of str, optional
        Names of all annotations of the objects to display in the graph as
        node attributes.
        Default: None
    attributes : tuple of str, optional
        Names of all attributes of the objects to display in the graph as
        node attributes.
        Default: None
    array_annotations : dict, optional
        For objects that have array annotations, select which arrays to be
        displayed in the graph as node attributes. The keys of the
        `array_annotations` parameter is the name of the object attribute
        that contains the array annotations dictionary. The values are which
        array annotations to display.
        Default: None
    strip_namespace : bool, optional
        If True, the namespaces (e.g. `attribute` in `'attribute:name'`) will
        be stripped, and the keys in the node attributes will be just the name
        (e.g., `'name'`).
        If False, the keys in the node attributes will be the full name
        (e.g. `'attribute:name'`).
        Default: True
    remove_none : bool, optional
        If True, the return nodes of functions that return `None` will be
        removed from the graph. This is useful to avoid cluttering if a
        function that returns None is called frequently.
        Default: True

    Attributes
    ----------
    graph : nx.DiGraph
        The NetworkX graph object representing the provenance read from the
        PROV file.
    """

    def __init__(self, prov_file, annotations=None, attributes=None,
                 array_annotations=None, strip_namespace=True,
                 remove_none=True, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Load PROV records and filter only the relevant for the construction
        # of the graph
        file_format = _get_prov_file_format(prov_file)
        doc = ProvDocument.deserialize(prov_file, format=file_format)
        filtered_doc = ProvDocument()
        for record in doc.get_records((ProvEntity, ProvActivity,
                                       ProvGeneration, ProvUsage,
                                       ProvMembership)):
            filtered_doc.add_record(record)

        prov_graph = prov_to_graph(filtered_doc)

        # Reverse direction of edges, as PROV format is from bottom to top
        reversed_prov_graph = prov_graph.reverse(copy=False)

        # Simplify the graph for visualization. The parameters passed to
        # the class initialization will control the graph output
        self.graph = self._transform_graph(reversed_prov_graph,
                                           annotations=annotations,
                                           attributes=attributes,
                                           array_annotations=array_annotations,
                                           strip_namespace=strip_namespace,
                                           remove_none=remove_none)

        # Nodes that are not directly connected to function call nodes, need
        # to have the execution counter set, so that the Gephi timeline
        # visualization works
        self._find_missing_intervals(self.graph)

        # Generate the interval according to Gephi format
        self._generate_interval_strings(self.graph)

    @staticmethod
    def _find_missing_intervals(graph):
        # Find all membership nodes and create a subgraph with the ancestors
        # and successors.
        # We will have all the spots where the execution counter was not set.
        # Then we build, for each path from the bottom to the top, the full
        # list with intervals at each node.
        processed_nodes = []
        subgraph_nodes = []
        for u, v, data in graph.edges(data=True):
            if data['membership']:
                subgraph_nodes.extend([u, v])

        subgraph = graph.subgraph(subgraph_nodes).reverse(copy=True)

        # We do progressively, changing the successors of the root nodes
        # each time, and generating a new subgraph until no nodes remain
        while not nx.is_empty(subgraph):
            root_nodes = [node for node in subgraph.nodes if
                          subgraph.in_degree(node) == 0]
            for root in root_nodes:
                successors = subgraph.successors(root)
                interval = subgraph.nodes[root]["gephi_interval"]
                for succ in successors:
                    graph.nodes[succ]["gephi_interval"].extend(interval)

            processed_nodes.extend(root_nodes)
            subgraph_nodes = []
            for u, v, data in graph.edges(data=True):
                if data['membership'] and v not in processed_nodes:
                    subgraph_nodes.extend([u, v])

            subgraph = graph.subgraph(subgraph_nodes).reverse(copy=True)

    @staticmethod
    def _generate_interval_strings(graph):
        for node, data in graph.nodes(data=True):
            data["gephi_interval"].sort(key=lambda tup: tup[0])
            segments = ";".join([f"[{start:.1f},{stop:.1f}]" for start, stop in
                                 data["gephi_interval"]])
            interval = f"<{segments}>"
            data["Time Interval"] = interval
            data.pop("gephi_interval")

    @staticmethod
    def _transform_graph(graph, annotations=None, attributes=None,
                         array_annotations=None, strip_namespace=True,
                         remove_none=True):
        # Transform a NetworkX graph obtained from the PROV data, so that the
        # visualization is simplified. A new `nx.DiGraph` object is created
        # and returned. Annotations and attributes of the entities stored in
        # the PROV file can be filtered.

        transformed = nx.DiGraph()
        none_nodes = []

        print("Transforming nodes")
        # Copy all the nodes, changing the URI to string and extracting the
        # requested attributes/annotations as node data.
        for node in graph.nodes:
            node_id = _get_id(node.identifier.uri)
            if remove_none and "builtins.NoneType" in node_id:
                none_nodes.append(node)
                continue
            data = _get_data(node, node_id,
                             annotations=annotations,
                             attributes=attributes,
                             array_annotations=array_annotations,
                             strip_namespace=strip_namespace)
            transformed.add_node(node_id, **data)

        print("Transforming edges")
        # Add all the edges.
        # If membership, the direction must be reversed.
        # If usage/generation, create additional nodes for the function call,
        # with the parameters as node data.
        # A membership flag is created, as this will be used.
        for u, v, data in graph.edges(data=True):
            if remove_none and len(none_nodes) > 0:
                if u in none_nodes or v in none_nodes:
                    continue

            u_id = _get_id(u.identifier.uri)
            v_id = _get_id(v.identifier.uri)

            relation = data['relation']
            if isinstance(relation, ProvMembership):
                membership_relation = _get_membership_relation(relation, graph)
                transformed.add_edge(v_id, u_id, membership=True,
                                     label=membership_relation)
            elif isinstance(relation, (ProvUsage, ProvGeneration)):
                node_id, node_data = _get_function_call_node(u_id, v_id,
                                                             relation)
                if not node_id in graph.nodes:
                    transformed.add_node(node_id, **node_data)

                if isinstance(relation, ProvUsage):
                    transformed.add_edge(u_id, node_id, membership=False)
                    _add_gephi_interval(transformed.nodes[u_id],
                                        node_data['execution_order'])
                else:
                    transformed.add_edge(node_id, v_id, membership=False)
                    _add_gephi_interval(transformed.nodes[v_id],
                                        node_data['execution_order'])

        print("Removing activities")
        # Remove old ProvActivity nodes that are not needed anymore
        # (unconnected). They were set with the `type` as `activity` in the
        # node data dictionary.
        filter_nodes = [node for node, data in transformed.nodes(data=True) if
                        data['type'] == "activity"]
        transformed.remove_nodes_from(filter_nodes)

        return transformed

    @staticmethod
    def _condense_memberships(graph, preserve=None):
        if preserve is None:
            preserve = []

        # Find all membership edges
        filter_edges = [tuple(e) for *e, data in graph.edges(data=True) if
                        data['membership']]

        # Iterate over the edges. We will contract if:
        #  - target does not have an edge to a function
        #  - target is not preserved

        remove_nodes = []
        replaced_edges = []

        while len(filter_edges) > 0:

            e = filter_edges.pop(0)
            if e in replaced_edges:
                continue
            u, v = e

            if graph.nodes[v]['label'] in preserve:
                continue

            successors = []
            input_to_function = False
            for successor in graph.successors(v):
                if graph.nodes[successor]['type'] == NSS_FUNCTION:
                    input_to_function = True
                    break
                successors.append(successor)
            if input_to_function:
                continue

            edge_data = graph.edges[e]

            # For each successor of node `v`, we connect with node `u`.
            # We push the replaced edges to processed edges, in case they are
            # also to be removed later.
            # Edge label is formed by concatenating the current edge with the
            # current value of `v` to the successor.
            # We add the new edge to the list to be processed, in case several
            # sequential memberships are being pruned.
            # Replaced edges are removed from the graph.
            for successor in successors:
                # Create new label
                replaced_edge = (v, successor)
                replaced_data = graph.edges[replaced_edge]
                new_edge_label = edge_data['label'] + replaced_data['label']
                replaced_data['label'] = new_edge_label

                # Create new edge
                new_edge = (u, successor)
                graph.add_edge(*new_edge, **replaced_data)
                filter_edges.append(new_edge)

                # Remove replaced edges
                graph.remove_edge(*replaced_edge)
                replaced_edges.append(replaced_edge)

            # Remove original edge
            graph.remove_edge(*e)

            if not v in remove_nodes:
                remove_nodes.append(v)

        # Remove the nodes
        for node in remove_nodes:
            graph.remove_node(node)

    def condense_memberships(self, preserve=None):
        """
        Condense sequential entity membership relationships into a single
        node. This operation is done in-place, i.e., the graph stored as
        :attr:`graph` will be modified.

        Parameters
        ----------
        preserve : tuple of str, optional
            List the labels of nodes that should not be condensed if present
            in a membership relationship.
            Default: None
        """
        self._condense_memberships(self.graph, preserve=preserve)

    def save_gexf(self, file_name):
        nx.write_gexf(self.graph, file_name)

    def save_graphml(self, file_name):
        nx.write_graphml(self.graph, file_name)
