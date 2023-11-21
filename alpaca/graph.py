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
import logging

import networkx as nx
from networkx.algorithms.summarization import (_snap_eligible_group,
                                               _snap_split)

from rdflib.namespace import RDF, PROV

from alpaca.ontology import ALPACA
from alpaca.serialization import AlpacaProvDocument
from alpaca.serialization.identifiers import (NSS_FUNCTION, NSS_FILE,
                                              entity_info, activity_info)
from alpaca.utils.files import _get_file_format


# Create logger and set configuration
logger = logging.getLogger(__file__)
log_handler = logging.StreamHandler()
log_handler.setFormatter(logging.Formatter("[%(asctime)s] alpaca.graph -"
                                           " %(levelname)s: %(message)s"))
logger.addHandler(log_handler)
logger.propagate = False


# String constants to use in the output
# These may be added to the names of `NameValuePair` information
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


def _get_function_call_data(activity, function_name, execution_order, params,
                            use_name_in_parameter=True,
                            use_class_in_name=True):

    data = activity_info(activity)
    label = function_name
    if not use_class_in_name:
        label = function_name.split(".")[-1]
    data['label'] = label
    data["execution_order"] = execution_order

    prefix = "parameter" if not use_name_in_parameter else data["label"]
    for param, value in params.items():
        data[f"{prefix}:{param}"] = value

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
                     strip_namespace=True, value_attribute=None):
    filter_map = defaultdict(list)

    filter_map.update(
        {ALPACA.hasAnnotation: annotations if annotations else [],
         ALPACA.hasAttribute: attributes if attributes else []})

    data = entity_info(entity)

    if annotations or attributes:
        for attr_type in (ALPACA.hasAttribute, ALPACA.hasAnnotation):
            for name_value_bnode in graph.objects(entity, attr_type):
                attr_name, attr_value = _get_name_value_pair(graph,
                                                             name_value_bnode)
                if (attr_name in filter_map[attr_type]) or \
                        filter_map[attr_type] == 'all':

                    _add_attribute(data, attr_name, attr_type, attr_value,
                                   strip_namespace)

    # Get the stored value if requested and present
    if value_attribute:
        value = graph.value(entity, PROV.value)
        if value:
            data[value_attribute] = value.toPython()

    if data['type'] == NSS_FILE:
        file_path = str(list(graph.objects(entity, ALPACA.filePath))[0])
        data["File_path"] = file_path

    return data


# Main graph class

class ProvenanceGraph:
    """
    Directed Acyclic Graph representing the provenance history stored in an
    RDF file structured with the Alpaca ontology.

    The visualization is based on NetworkX, and the graph can be accessed
    through the :attr:`graph` attribute.

    `DataObjectEntity` and `FileEntity` individuals are nodes, identified with
    the respective URIs. `FunctionExecution` activities are also loaded as
    nodes. Each of the three node types is identified by the `type` node
    attribute. Interval strings for timeline visualization in Gephi are
    provided as the `Time Interval` node attribute.

    Each node has an attributes dictionary with general description:

    * for `DataObjectEntity`, the `label` node attribute contains the Python
      class name of the object (e.g., `ndarray`). The `Python_name` node
      attribute contains the full path to the class in the package (e.g.,
      `numpy.ndarray`);
    * for `FileEntity`, the `label` node attribute is `File`;
    * for `FunctionExecution` activities, the `label` will be the function
      name (e.g. `mean`), and the `Python_name` node attribute will be the
      full path to the function in the package (e.g., `numpy.mean`).

    Each node may also have additional attributes in the dictionary, with
    extended information:

    * for `DataObjectEntity`, it contains the Python object attributes and
      annotations that were saved as metadata in the PROV file;
    * for `FileEntity`, it contains the file information such as path and hash;
    * for `FunctionExecution` activities, it contains the values of the
      parameters used to call the function.

    The node attributes to be included are selected by the `annotations` and
    `attributes` parameters during the initialization.

    Finally, the graph can be simplified using methods for condensing
    memberships (e.g., elements inside lists) and simplification (e.g.,
    repeated operation in tracks generated from loops).

    Parameters
    ----------
    prov_file : str or Path-like
        Source file(s) with RDF provenance data in the Alpaca format based on
        W3C PROV-O. If multiple files are provided, all will be loaded into
        the same graph object. This is useful to integrate provenance captured
        from several sources for visualization (e.g., steps in workflows
        or parallel processes).
    annotations : tuple of str or 'all', optional
        Names of all annotations of the objects to display in the graph as
        node attributes. Annotations are defined as values of an annotation
        dictionary that might be present in the object (e.g., Neo objects).
        In the PROV file, they are identified with the `hasAnnotation`
        property in individuals of the `DataObjectEntity` class. If `'all'`,
        all the annotations in the objects are going to be included.
        Default: None
    attributes : tuple of str or 'all', optional
        Names of all attributes of the objects to display in the graph as
        node attributes. Attributes are regular Python object attributes.
        In the PROV file, they are identified with the `hasAttribute`
        property in individuals of the `DataObjectEntity` class.  If `'all'`,
        all the attributes in the objects are going to be included.
        Default: None
    strip_namespace : bool, optional
        If False, the namespaces (i.e., `attribute` or `annotation`) will
        be shown for each requested attribute/annotation. For example, for an
        attribute `'shape'`, if `strip_namespace` is False, the key in the node
        attributes will be the full name `'attribute:shape'`. If True, the key
        in the node attributes will be just `'shape'`. The namespaces are
        `annotation` and `attribute` for object annotations and attributes,
        respectively.
        Default: True
    remove_none : bool, optional
        If True, the return nodes of functions that return `None` will be
        removed from the graph. This is useful to avoid cluttering if a
        function that returns None is called frequently.
        Default: True
    use_name_in_parameter : bool, optional
        If True, the function name will be added to the parameter name in the
        node attributes (e.g., `'function:param'`). If False, the parameter
        name will be shown with a generic tag (e.g., `'parameter:param'`). Use
        this option if different functions share same parameter names, to avoid
        ambiguity.
        Default: True
    use_class_in_method_name : bool, optional
        If True, function nodes that are methods in classes will be labeled
        with the class name as prefix (e.g., `ClassName.method_name`). If
        False, only the method name will appear in the node label (e.g.,
        `method_name`).
        Default: True
    time_intervals : bool, optional
        If True, the nodes will have the `Time Interval` attribute containing
        time interval strings in the format supported by the Gephi timeline
        feature. If False, the attribute is not included.
        Default: True
    value_attribute : str, optional
        If provided, an attribute named `value_attribute` will be added to
        the node attributes to show the values stored in the provenance
        information. Alpaca stores the values of objects of the builtin types
        `str`, `bool`, `int`, `float` and `complex`, as well as the NumPy
        numeric types (e.g. `numpy.float64`) by default. The values of
        additional types can be defined using the
        :func:`alpaca.settings.alpaca_setting` function.
        Default: None

    Attributes
    ----------
    graph : nx.DiGraph
        The NetworkX graph object representing the provenance read from the
        PROV file.

    """

    def __init__(self, *prov_file, annotations=None, attributes=None,
                 strip_namespace=True, remove_none=True,
                 use_name_in_parameter=True, use_class_in_method_name=True,
                 time_intervals=True, value_attribute=None):

        # Load PROV records from the file(s)
        doc = AlpacaProvDocument()
        for file in prov_file:
            doc.read_records(file, file_format=None)

        # Transform RDFlib graph to NetworkX and simplify the graph for
        # visualization. The parameters passed to the class initialization
        # will control the graph output
        self.graph = self._transform_graph(
            doc.graph, annotations=annotations, attributes=attributes,
            strip_namespace=strip_namespace, remove_none=remove_none,
            use_name_in_parameter=use_name_in_parameter,
            use_class_in_method_name=use_class_in_method_name,
            time_intervals=time_intervals, value_attribute=value_attribute
        )

        if time_intervals:
            # Nodes that are not directly connected to function call nodes,
            # need to have the execution counter set, so that the Gephi
            # timeline visualization works
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
                    attrs = graph.nodes[succ]
                    if not "gephi_interval" in attrs:
                        attrs["gephi_interval"] = []
                    attrs["gephi_interval"].extend(interval)

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
                         strip_namespace=True, remove_none=True,
                         use_name_in_parameter=True,
                         use_class_in_method_name=True,
                         time_intervals=True, value_attribute=None):
        # Transform an RDFlib graph obtained from the PROV data, so that the
        # visualization is simplified. A new `nx.DiGraph` object is created
        # and returned. Annotations and attributes of the entities stored in
        # the PROV file can be filtered.

        transformed = nx.DiGraph()
        none_nodes = []

        logger.debug("Creating nodes")

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
                                    strip_namespace=strip_namespace,
                                    value_attribute=value_attribute)
            transformed.add_node(node_id, **data)

        # Add all the edges.
        # If usage/generation, create additional nodes for the function call,
        # with the parameters as node data.
        # If membership, membership flag is set to True, as this will be used.
        logger.debug("Creating edges")

        for s, func_execution in graph.subject_objects(PROV.wasGeneratedBy):

            target = str(s)

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

            # Function description
            function = list(
                graph.objects(func_execution, ALPACA.usedFunction))[0]
            function_name = list(
                graph.objects(function, ALPACA.functionName))[0].value

            # Get the entity(ies) used for this generation
            source_entities = list()
            for entity in graph.objects(func_execution, PROV.used):
                source_entities.append(str(entity))

            node_data = _get_function_call_data(activity=func_execution,
                function_name=function_name,
                execution_order=execution_order, params=params,
                use_name_in_parameter=use_name_in_parameter,
                use_class_in_name=use_class_in_method_name)

            if time_intervals:
                _add_gephi_interval(node_data, node_data["execution_order"])

            # Add a new node for the function execution, with the activity
            # data
            node_id = str(func_execution)
            if not node_id in transformed.nodes:
                transformed.add_node(node_id, **node_data)

            # Add all the edges from sources to activity and from activity
            # to targets
            for source in source_entities:
                transformed.add_edge(source, node_id, membership=False)
                if time_intervals:
                    _add_gephi_interval(transformed.nodes[source],
                                    node_data['execution_order'])

            if not remove_none or (remove_none and target not in none_nodes):
                transformed.add_edge(node_id, target, membership=False)
                if time_intervals:
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
    def _snap_build_graph(graph, groups, neighbor_info, remove_attributes,
                          record_members=True):
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
                if remove_attributes is None or key not in remove_attributes
            }

            # Organize time intervals
            if 'Time Interval' in attributes:
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

            count = len(group_set)
            supernode_attributes['member_count'] = count

            # Save a string with the identifiers of all member nodes if
            # requested
            if record_members:
                supernode_attributes['members'] = ";".join(group_set)

            output.add_node(supernode, **supernode_attributes)

        for group_id in groups:
            group_set = groups[group_id]
            source_supernode = node_label_lookup[group_id]
            for other_group, group_edge_types in neighbor_info[
                next(iter(group_set))
            ].items():
                if group_edge_types:
                    target_supernode = node_label_lookup[other_group]
                    summary_graph_edge = (source_supernode, target_supernode)

                    superedge_attributes = {}
                    output.add_edge(*summary_graph_edge,
                                    **superedge_attributes)

        return output

    def aggregate(self, group_node_attributes, use_function_parameters=True,
                  output_file=None, remove_attributes=None,
                  record_members=True):
        """
        Creates a summary graph based on a selection of attributes of the
        nodes in the graph.

        The attributes can be individualized for each
        node label (as defined by the `label` node attribute), so that
        different levels of aggregation are possible. Therefore, it is
        possible to generate visualizations with different levels of detail
        to progressively inspect the provenance trace.

        In the summarized nodes, the `member_count` node attribute stores the
        number of nodes in the group. If requested, the list with the IDs of
        the original nodes that are part of that group can be stored in the
        `members` node attribute.

        Parameters
        ----------
        group_node_attributes : dict
            Dictionary selecting which attributes are used in the aggregation.
            The keys are the possible labels in the graph, and the values
            are tuples of the node attributes or callables used for
            determining supernodes.

            For example, to aggregate `Quantity` nodes based on different
            `shape` attribute values, `group_node_attributes` would be
            `{'Quantity': ('shape',)}`. If passing an empty dictionary, no
            attributes will be considered, and the aggregation will be based
            on the topology (i.e., nodes at similar levels will be grouped
            according to the connectivity).

            In addition to attribute names, callables that take the
            arguments `(graph, node, data)`, where `graph` is the graph being
            aggregated, `node` is the node being evaluated for grouping, and
            `data` is the dictionary of attributes, can be used. The returned
            value is used to define the group. This allows flexibility when
            grouping, as attribute values can be transformed (e.g., extracting
            a token such as file extension from an attribute that stores the
            path as a string), or the relationship of the node to neighbors
            and values of edges can be checked. However, this will increase
            the time to evaluate the grouping criteria of a node.
        use_function_parameters : bool, optional
            If True, the parameters of function nodes in the graph will be
            considered in the aggregation, i.e., if the same function is called
            with different parameters, different supernodes will be generated.
            If False, a single supernode will be produced, regardless of the
            different parameters used.
            Default: True
        output_file : str or Path-like, optional
            If None, a `nx.DiGraph` object will be returned. If not None, the
            graph will be saved in the provided path, and the function will
            return None. The file must have either the `.gexf` or the
            `.graphml` extension, to save as either GEXF or GraphML formats
            respectively.
            Default: None
        remove_attributes : str or tuple of str, optional
            Remove the specified node attributes from the aggregated graph.
            Default: None
        record_members : bool, optional
            If True, the summarized nodes will have the `members` attribute
            with the identifiers of all nodes that are part of the group.
            Default: True

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
            If `output_file` is not None and the file does not have either
            `'.gexf'` or `'.graphml'` as extension.

        Notes
        -----
        This function is an adaptation of the `snap_aggregation` function
        included in NetworkX 2.6, which implemented the SNAP algorithm based on
        [1]_.

        The function was modified to group the nodes based on different
        attributes or callables (using a dictionary based on the labels)
        instead of attributes that are common to all nodes.

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

        def _fetch_group_tuple(graph, node, data, label, data_attributes,
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
                    # selected attributes/callables. Otherwise, we will use
                    # the label only

                    for attr in data_attributes:

                        if callable(attr):
                            # We have requested grouping using a function that
                            # takes the graph, the node, and the node
                            # attributes as parameters. This allows a more
                            # customized filtering, that can extract specific
                            # information from the attribute value or use the
                            # node relationships
                            group_info.append(attr(graph, node, data))
                        else:
                            # Fetch the attribute value for this node, if
                            # available
                            group_info.append(data.get(attr, None))

            return tuple(group_info)

        # We don't consider edges
        edge_types = {edge: () for edge in self.graph.edges}

        # Create the groups based on the selected conditions
        group_lookup = {
            node: _fetch_group_tuple(
                self.graph, node, attrs, attrs['label'],
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

        aggregated = self._snap_build_graph(self.graph, groups, neighbor_info,
                                            remove_attributes,
                                            record_members=record_members)

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

    def remove_attributes(self, *attributes):
        """
        Remove one or more attributes from the nodes.

        Parameters
        ----------
        attributes : str
            Key(s) identifying the attribute(s) to be removed from the node
            attribute dictionary.
        """
        if len(attributes) > 1:
            for _, node_attrs in self.graph.nodes(data=True):
                for attr in attributes:
                    node_attrs.pop(attr, None)
        else:
            # Algorithm has O(N) complexity. In the case of a single attribute,
            # there is no need for a nested loop, which will improve run time.
            attr = attributes[0]
            for _, node_attrs in self.graph.nodes(data=True):
                node_attrs.pop(attr, None)

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
