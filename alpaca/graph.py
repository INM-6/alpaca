"""
This class reads a file with serialized provenance data into a NetworkX graph.

It provides functionality for manipulating the graph to simplify the
visualization, and also to select which details of the captured information
will be displayed as node attributes. Finally, it allows saving the graph in
formats used by graph visualization software, such as GEXF or GraphML.

See the :ref:`visualization` section on the `Installation` section,
for instructions on how to download and setup Gephi that can be used to
visualize GEXF files.

.. autoclass:: alpaca.ProvenanceGraph
    :members:

"""


import re
from itertools import chain
from collections import defaultdict

import networkx as nx
from networkx.algorithms.summarization import (_snap_eligible_group,
                                               _snap_split)

from rdflib.namespace import RDF, PROV

from alpaca.ontology import ALPACA
from alpaca.serialization import AlpacaProvDocument
from alpaca.serialization.identifiers import (NSS_FUNCTION, NSS_FILE,
                                              entity_info, activity_info)
from alpaca.utils.files import _get_file_format


# String constants to use in the output
# These may be added to the names of NameValuePair information
PREFIX_ATTRIBUTE = "attribute"
PREFIX_ANNOTATION = "annotation"
PREFIX_PARAMETER = "parameter"


# Mapping of ontology predicates to the prefixes
ATTR_NAMES = {ALPACA.hasAttribute: PREFIX_ATTRIBUTE,
              ALPACA.hasAnnotation: PREFIX_ANNOTATION,
              ALPACA.hasParameter: PREFIX_PARAMETER}


def _add_gephi_interval(data, order):
    if not "gephi_interval" in data:
        data["gephi_interval"] = []
    data["gephi_interval"].append((order, order))


def _get_function_call_data(activity, execution_order, params,
                            use_name_in_parameter=True):

    data = activity_info(activity)
    data["execution_order"] = execution_order

    prefix = "parameter" if not use_name_in_parameter else data["label"]
    for param, value in params.items():
        data[f"{prefix}:{param}"] = value

    _add_gephi_interval(data, data["execution_order"])

    return data


def _add_attribute(data, attr_name, attr_type, attr_value, strip_namespace):
    if not strip_namespace:
        attr_name = f"{ATTR_NAMES[attr_type]}:{attr_name}"

    if attr_name in data:
        raise ValueError(
            "Duplicate property values. Make sure to include the namespaces!")
    data[attr_name] = attr_value


def _get_name_value_pair(graph, bnode):
    # Read name and value from the NameValuePair blank node
    attr_name = str(list(graph.objects(bnode, ALPACA.pairName))[0])
    attr_value = str(list(graph.objects(bnode, ALPACA.pairValue))[0])
    return attr_name, attr_value


def _get_entity_data(graph, entity, annotations=None, attributes=None,
                     array_annotations=None, strip_namespace=True):
    filter_map = defaultdict(list)

    # Array annotations is a special attribute that stores a dictionary
    # We will retrieve it as an ordinary attribute value, and then
    # process later
    if array_annotations:
        attributes = attributes + tuple(array_annotations.keys())

    filter_map.update(
        {ALPACA.hasAnnotation: annotations,
         ALPACA.hasAttribute: attributes})

    data = entity_info(entity)
    data["gephi_interval"] = []

    if annotations or attributes or array_annotations:
        for attr_type in (ALPACA.hasAttribute, ALPACA.hasAnnotation):
            for name_value_bnode in graph.objects(entity, attr_type):
                attr_name, attr_value = _get_name_value_pair(graph,
                                                             name_value_bnode)
                if attr_name in filter_map[attr_type]:

                    if array_annotations and attr_name in array_annotations:
                        # Extract the relevant keys from the array annotations
                        # string
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

    if data['type'] == NSS_FILE:
        file_path = str(list(graph.objects(entity, ALPACA.filePath))[0])
        data["File_path"] = file_path

    return data


# Main graph class

class ProvenanceGraph:
    """
    Directed Acyclic Graph representing the provenance history stored in a
    PROV file with the Alpaca ontology.

    The visualization is based on NetworkX, and the graph can be accessed
    through the :attr:`graph` attribute.

    `DataObjectEntity` and `FileEntity` individuals are nodes, identified with
    the respective persistent identifiers. `Function` activities are also
    loaded as nodes. Each of the three node types is identified by the `type`
    node attribute. Interval strings for timeline visualization in Gephi are
    provided as the `Time Interval` node attribute.

    Each node has an attributes dictionary with general description:

    * for `DataObjectEntity`, the `Label` node attribute contains the Python
      class name of the object (e.g., `ndarray`). The `Python_name` node
      attribute contains the full path to the class in the package (e.g.,
      `numpy.ndarray`);
    * for `FileEntity`, the `Label` node attribute is `File`;
    * for `Function` activities, the `Label` will be the function name (e.g.
      `mean`), and the `Python_name` node attribute will be the full path to
      the function in the package (e.g., `numpy.mean`).

    Each node may also have additional attributes in the dictionary, with
    extended information:

    * for `DataObjectEntity`, it contains the Python object attributes and
      annotations that were saved as metadata in the PROV file;
    * for `FileEntity`, it contains the file information such as path and hash;
    * for `FunctionExecution` activities, it contains the values of the
      parameters used to call the function.

    The attributes to be included are selected by the `annotations`,
    `attributes`, and `array_annotations` parameters during the initialization.

    Finally, the graph can be simplified using methods for condensing
    memberships (e.g., elements inside lists) and simplification (e.g.,
    repeated operation in tracks generated from loops).

    Parameters
    ----------
    prov_file : str or Path-like
        Source file with provenance data in the Alpaca format based on W3C
        PROV-O.
    annotations : tuple of str, optional
        Names of all annotations of the objects to display in the graph as
        node attributes. Annotations are defined as values of an annotation
        dictionary that might be present in the object (e.g., Neo objects).
        In the PROV file, they are identified with the `hasAnnotation`
        property in individuals of the `DataObjectEntity` class.
        Default: None
    attributes : tuple of str, optional
        Names of all attributes of the objects to display in the graph as
        node attributes. Attributes are regular Python object attributes.
        In the PROV file, they are identified with the `hasAttribute`
        property in individuals of the `DataObjectEntity` class.
        Default: None
    array_annotations : dict, optional
        For objects that have array annotations, select which arrays to be
        displayed in the graph as node attributes. The keys of the
        `array_annotations` dictionary is the name of the Python object
        attribute that contains the array annotations dictionary.
        The values of the dictionary are which array annotations to display.
        Default: None
    strip_namespace : bool, optional
        If True, the namespaces (e.g. `attribute` in `'attribute:name'`) will
        be stripped, and the keys in the node attributes will be just the name
        (e.g., `'name'`).
        If False, the keys in the node attributes will be the full name
        (e.g. `'attribute:name'`). The namespaces are `annotation` and
        `attribute` for object annotations and attributes, respectively.
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

        # Load PROV records from the file
        doc = AlpacaProvDocument()
        doc.read_records(prov_file, file_format=None)

        # Transform RDFlib graph to NetworkX and simplify the graph for
        # visualization. The parameters passed to the class initialization
        # will control the graph output
        self.graph = self._transform_graph(doc.graph,
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
        # Create a Gephi interval string (e.g. "<[start:end];[start:end]>")
        # for each node in `graph`, and add as additional node data, using
        # the "Time Interval" label.

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
                         remove_none=True, use_name_in_parameter=True):
        # Transform an RDFlib graph obtained from the PROV data, so that the
        # visualization is simplified. A new `nx.DiGraph` object is created
        # and returned. Annotations and attributes of the entities stored in
        # the PROV file can be filtered.

        transformed = nx.DiGraph()
        none_nodes = []

        print("Creating nodes")

        # Copy all the Entity nodes, while adding the requested attributes and
        # annotations as node data.
        for entity in chain(graph.subjects(RDF.type, ALPACA.DataObjectEntity),
                            graph.subjects(RDF.type, ALPACA.FileEntity)):
            node_id = str(entity)
            if remove_none and "builtins.NoneType" in node_id:
                none_nodes.append(node_id)
                continue
            data = _get_entity_data(graph, entity,
                                    annotations=annotations,
                                    attributes=attributes,
                                    array_annotations=array_annotations,
                                    strip_namespace=strip_namespace)
            transformed.add_node(node_id, **data)

        print("Creating edges")
        # Add all the edges.
        # If usage/generation, create additional nodes for the function call,
        # with the parameters as node data.
        # If membership, membership flag is set to True, as this will be used.

        for s, func_execution in graph.subject_objects(PROV.wasGeneratedBy):

            target = str(s)
            if remove_none and len(none_nodes) > 0:
                if target in none_nodes:
                    continue

            # Extract all the parameters of the function execution
            params = dict()
            for parameter in graph.objects(func_execution,
                                           ALPACA.hasParameter):
                name, value = _get_name_value_pair(graph, parameter)
                params[name] = value

            # Execution order
            execution_order = list(
                graph.objects(func_execution,
                              ALPACA.executionOrder))[0].value

            # Get the entity(ies) used for this generation
            source_entities = list()
            for entity in graph.objects(func_execution, PROV.used):
                source_entities.append(str(entity))

            node_data = _get_function_call_data(activity=func_execution,
                execution_order=execution_order, params=params,
                use_name_in_parameter=use_name_in_parameter)

            # Add a new node for the function execution, with the activity
            # data
            node_id = str(func_execution)
            if not node_id in transformed.nodes:
                transformed.add_node(node_id, **node_data)

            # Add all the edges from sources to activity and from activity
            # to targets
            for source in source_entities:
                transformed.add_edge(source, node_id, membership=False)
                _add_gephi_interval(transformed.nodes[source],
                                    node_data['execution_order'])

            transformed.add_edge(node_id, target, membership=False)
            _add_gephi_interval(transformed.nodes[target],
                                node_data['execution_order'])

        for container, member in graph.subject_objects(PROV.hadMember):

            membership_relation = None
            for predicate, object in graph.predicate_objects(member):
                if predicate in [ALPACA.containerIndex, ALPACA.containerSlice]:
                    membership_relation = f"[{str(object)}]"
                elif predicate == ALPACA.fromAttribute:
                    membership_relation = f".{str(object)}"

            if membership_relation is None:
                raise ValueError("Membership information not found for"
                                 f"{container}->{member} relation.")

            transformed.add_edge(str(container), str(member), membership=True,
                                 label=membership_relation)

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

        Membership relationships are used to describe relationships such as
        attributes (e.g. `block.segments`) or membership in containers (e.g.,
        `spiketrains[0]`).

        Parameters
        ----------
        preserve : tuple of str, optional
            List the labels of nodes that should not be condensed if present
            in a membership relationship.
            Default: None
        """
        self._condense_memberships(self.graph, preserve=preserve)

    @staticmethod
    def _snap_build_graph(graph, groups, neighbor_info):
        # Function modified from NetworkX 2.6, to build the aggregated graph
        # after SNAP aggregation.
        #
        # Please refer to the `Acknowledgements and open source software`
        # section for copyright and license information.

        def _aggregate_attributes(source, group_iterator):
            raw_attributes = defaultdict(set)
            for member in group_iterator:
                for attr, value in source[member].items():
                    raw_attributes[attr].add(value)

            # Transform all elements values to strings
            attributes = {
                key: str(next(iter(value)))
                if len(value) == 1 else ";".join(map(str, sorted(list(value))))
                for key, value in raw_attributes.items()
            }

            # Organize time intervals
            intervals = re.findall(r"(\[[\d+.,]+\])",
                                   attributes['Time Interval'])
            intervals.sort()
            intervals_str = ";".join(intervals)
            attributes['Time Interval'] = f"<{intervals_str}>"

            return attributes

        output = nx.DiGraph()
        prefix = "Step"
        node_label_lookup = dict()

        for index, group_id in enumerate(groups):
            group_set = groups[group_id]
            supernode = f"{prefix} {index}"
            node_label_lookup[group_id] = supernode

            # We sumarize all possible values for all attributes in the nodes
            # from the group
            supernode_attributes = _aggregate_attributes(graph.nodes,
                                                         group_set)

            # Save a string with the identifiers of all member nodes
            members = ";".join(group_set)

            output.add_node(supernode, members=members, **supernode_attributes)

        for group_id in groups:
            group_set = groups[group_id]
            source_supernode = node_label_lookup[group_id]
            for other_group, group_edge_types in neighbor_info[
                next(iter(group_set))
            ].items():
                if group_edge_types:
                    target_supernode = node_label_lookup[other_group]
                    summary_graph_edge = (source_supernode, target_supernode)

                    # TODO: add edge weight and summarize attributes
                    superedge_attributes = {}
                    output.add_edge(*summary_graph_edge,
                                    **superedge_attributes)

        return output

    def aggregate(self, group_node_attributes, use_function_parameters=True,
                  output_file=None):
        """
        Creates a summary graph based on a selection of attributes of the
        nodes in the graph.

        The attributes can be individualized for each
        node label (as defined by the `Label` node attribute), so that
        different levels of aggregation are possible. Therefore, it is
        possible to generate visualizations with different levels of detail
        to progressively inspect the provenance trace.

        Parameters
        ----------
        group_node_attributes : dict
            Dictionary selecting which attributes are used in the aggregation.
            The keys are the possible labels in the graph, and the values
            are tuples of the node attributes used for determining supernodes.
            For example, to aggregate `Quantity` nodes based on different
            `shape` attribute values, `group_node_attributes` would be
            `{'Quantity': ('shape',)}`. If passing an empty dictionary, no
            attributes will be considered, and the aggregation will be based
            on the topology (i.e., nodes at similar levels will be grouped
            according to the connectivity).
        use_function_parameters : bool, optional
            If True, the parameters of function nodes in the graph will be
            considered in the aggregation, i.e., if the same function is called
            with different parameters, different supernodes will be generated.
            If False, a single supernode will be produced, regardless of the
            different parameters used.
            Default: True
        output_file : str or Path-like
            If None, a `nx.DiGraph` object will be returned. If not None, the
            graph will be saved in the provided path, and the function will
            return None. The file must have either the `.gexf` or the
            `.graphml` extension, to save as either GEXF or GraphML formats
            respectively.

        Returns
        -------
        nx.DiGraph or None
            If an output file was not specified in `output_file`, returns the
            aggregated graph as a NetworkX object. The original graph stored
            in :attr:`graph` is not modified.
            If an output file was specified, returns None.

        Raises
        ------
        ValueError
            If 'output_file` is not None and the file does not have either
            '.gexf' or '.graphml' as extension.

        Notes
        -----
        This function is an adaptation of the `snap_aggregation` function
        included in NetworkX 2.6, which implemented the SNAP algorithm based on
        [1]_.

        The function was modified to group the nodes based on different
        attributes  (using a dictionary based on the labels) instead of a
        single attribute that is common to all nodes.

        During the summary graph generation, the attribute values are also
        summarized, so that the user has an idea of all the possible values in
        the group.

        Please refer to the :ref:`open_software_licenses` section for copyright
        and license information.

        References
        ----------
        .. [1] Y. Tian, R. A. Hankins, and J. M. Patel. Efficient aggregation
           for graph summarization. In Proc. 2008 ACM-SIGMOD Int. Conf.
           Management of Data (SIGMOD’08), pages 567–580, Vancouver, Canada,
           June 2008.
        """

        def _fetch_group_tuple(data, label, data_attributes,
                               use_function_params):
            group_info = [label]

            # If function, we use all the parameters
            if data['type'] == NSS_FUNCTION and use_function_params:
                parameters = [name for name in data.keys()
                              if name.startswith("parameter:") or
                              name.startswith(f"{label}:")]
                parameters.sort()
                for attr in parameters:
                    group_info.append(data[attr])
            else:
                if data_attributes is not None:
                    # We have requested grouping for this object based on
                    # selected attributes. Otherwise, we will use the label
                    for attr in data_attributes:
                        group_info.append(data[attr])
            return tuple(group_info)

        # We don't consider edges
        edge_types = {edge: () for edge in self.graph.edges}

        # Create the groups based on the selected conditions
        group_lookup = {
            node: _fetch_group_tuple(attrs, attrs['label'],
                group_node_attributes.get(attrs['label'], None),
                use_function_parameters)
            for node, attrs in self.graph.nodes.items()
        }

        groups = defaultdict(set)
        for node, node_type in group_lookup.items():
            groups[node_type].add(node)

        eligible_group_id, neighbor_info = _snap_eligible_group(
            self.graph, groups, group_lookup, edge_types=edge_types)
        while eligible_group_id:
            groups = _snap_split(groups, neighbor_info, group_lookup,
                                 eligible_group_id)
            eligible_group_id, neighbor_info = _snap_eligible_group(
                self.graph, groups, group_lookup, edge_types=edge_types)

        aggregated = self._snap_build_graph(self.graph, groups, neighbor_info)

        if output_file is None:
            return aggregated

        file_format = _get_file_format(output_file)
        if file_format == "gexf":
            nx.write_gexf(aggregated, output_file)
        elif file_format == "graphml":
            nx.write_graphml(aggregated, output_file)
        else:
            raise ValueError("Unknown graph format. Please provide an output"
                             "file with either '.gexf' or '.graphml'"
                             "extension")

    def save_gexf(self, file_name):
        """
        Writes the current provenance graph as a GEXF file.
        """
        nx.write_gexf(self.graph, file_name)

    def save_graphml(self, file_name):
        """
        Writes the current provenance graph as a GraphML file.
        """
        nx.write_graphml(self.graph, file_name)
