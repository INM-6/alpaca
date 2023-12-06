"""
This class provides functionality to serialize/deserialize the provenance
using an ontology based on the W3C Provenance Ontology (PROV-O). The Alpaca
ontology is used to serialize the provenance information captured by Alpaca as
RDF files.

.. autoclass:: alpaca.AlpacaProvDocument
    :members:

"""

from itertools import product, chain
import numpy as np
import numbers

from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF, PROV, XSD

from alpaca.ontology import ALPACA
from alpaca.serialization.identifiers import (data_object_identifier,
                                              file_identifier,
                                              function_identifier,
                                              script_identifier,
                                              execution_identifier,
                                              _get_function_name)
from alpaca.serialization.converters import _ensure_type
from alpaca.serialization.neo import _neo_object_metadata

from alpaca.utils.files import _get_prov_file_format
from alpaca.alpaca_types import DataObject, File, Container
from alpaca.settings import _ALPACA_SETTINGS
from alpaca.ontology.annotation import _OntologyInformation, ONTOLOGY_INFORMATION

from tqdm import tqdm


def _add_name_value_pair(graph, uri, predicate, name, value):
    # Add a relationship defined by `predicate` using a blank node as object.
    # The object will be of type `alpaca:NameValuePair`.
    blank_node = BNode()
    graph.add((uri, predicate, blank_node))
    graph.add((blank_node, RDF.type, ALPACA.NameValuePair))
    graph.add((blank_node, ALPACA.pairName, Literal(name)))
    graph.add((blank_node, ALPACA.pairValue, Literal(value)))
    return blank_node


class AlpacaProvDocument(object):
    """
    Generates a file using the Alpaca ontology (based on W3C PROV-O) from
    the history records captured during the execution of a Python script,
    or reads a serialized file into an RDF graph object.

    Attributes
    ----------
    graph : rdflib.Graph
        Provenance data represented as an RDF graph, using the Alpaca ontology
        based on PROV-O.

    Notes
    -----
    For convenience, you can serialize the active history easily by just using
    the :func:`save_provenance` in :ref:`interface`. This class should
    be used only if you want to access the data as an RDF graph or to manually
    control the serialization.
    """

    XSD_TYPES = {
        numbers.Integral: XSD.integer,
        numbers.Real: XSD.double,
        numbers.Complex: XSD.string,
        str: XSD.string,
        bool: XSD.boolean,
    }

    def __init__(self):
        self.graph = Graph()
        namespace_manager = self.graph.namespace_manager
        namespace_manager.bind('alpaca', ALPACA)
        namespace_manager.bind('prov', PROV)
        self._authority = _ALPACA_SETTINGS['authority']

        # Gets all OntologyInformation objects generated with annotation
        # information during the run. Update the current graph namespaces
        # accordingly
        _OntologyInformation.bind_namespaces(namespace_manager)

        # Metadata plugins are used for packages (e.g., Neo) that require
        # special handling of metadata when adding to the PROV records.
        # Plugins are external functions that take the graph, the object URI,
        # and the metadata dict as parameters. The function should return a
        # dictionary mapping all blank nodes generated to represent attributes
        # and annotations, to allow the use of any semantic information
        # defined by ontology annotations (i.e., __ontology__ attribute).
        self._metadata_plugins = {
            'neo': _neo_object_metadata
        }

        # Set to store all entity URIs that are added to the graph, so that
        # there is a fast lookup
        self._entity_uris = set()

        # Store functions that have container output ontology annotations,
        # To add the identification to the objects after the graph is built
        self._container_output_functions = {}
        for obj_type, info in ONTOLOGY_INFORMATION.items():
            container_returns = info.get_container_returns()
            if container_returns:
                self._container_output_functions[obj_type] = container_returns

    # PROV relationships methods

    def _wasAttributedTo(self, entity, agent):
        self.graph.add((entity, PROV.wasAttributedTo, agent))

    def _wasAssociatedWith(self, activity, agent):
        self.graph.add((activity, PROV.wasAssociatedWith, agent))

    def _wasDerivedFrom(self, used_entity, generated_entity):
        self.graph.add((generated_entity, PROV.wasDerivedFrom, used_entity))

    def _wasGeneratedBy(self, entity, activity):
        self.graph.add((entity, PROV.wasGeneratedBy, activity))

    def _used(self, activity, entity):
        self.graph.add((activity, PROV.used, entity))

    # Agent methods

    def _add_ScriptAgent(self, script_info, session_id):
        # Adds a ScriptAgent record from the Alpaca PROV model
        uri = URIRef(script_identifier(script_info, session_id,
                                       self._authority))
        self.graph.add((uri, RDF.type, ALPACA.ScriptAgent))
        self.graph.add((uri, ALPACA.scriptPath, Literal(script_info.path)))
        return uri

    # Activity methods

    def _add_Function(self, function_info):
        # Adds a Function record from the Alpaca PROV model
        uri = URIRef(function_identifier(function_info, self._authority))
        self.graph.add((uri, RDF.type, ALPACA.Function))
        self.graph.add((uri, ALPACA.functionName,
                        Literal(function_info.name)))
        self.graph.add((uri, ALPACA.implementedIn,
                        Literal(function_info.module)))
        self.graph.add((uri, ALPACA.functionVersion,
                        Literal(function_info.version)))
        return uri

    def _add_ontology_information(self, target_uri, ontology_info,
                                  information_type, element=None):
        class_info = ontology_info.get_uri(information_type, element)
        if class_info:
            if isinstance(class_info, list):
                for class_uri in class_info:
                    self.graph.add((target_uri, RDF.type, class_uri))
            else:
                self.graph.add((target_uri, RDF.type, class_info))

    def _add_FunctionExecution(self, script_info, session_id, execution_id,
                               function_info, params, execution_order,
                               code_statement, start, end, function,
                               ontology_info=None):
        # Adds a FunctionExecution record from the Alpaca PROV model
        uri = URIRef(execution_identifier(
            script_info, function_info, session_id, execution_id,
            self._authority))
        self.graph.add((uri, RDF.type, ALPACA.FunctionExecution))

        if ontology_info:
            self._add_ontology_information(uri, ontology_info, 'function')

        self.graph.add((uri, PROV.startedAtTime,
                        Literal(start, datatype=XSD.dateTime)))
        self.graph.add((uri, PROV.endedAtTime,
                        Literal(end, datatype=XSD.dateTime)))
        self.graph.add((uri, ALPACA.codeStatement, Literal(code_statement)))
        self.graph.add((uri, ALPACA.executionOrder,
                        Literal(execution_order, datatype=XSD.integer)))
        self.graph.add((uri, ALPACA.usedFunction, function))

        for name, value in params.items():
            value = _ensure_type(value)
            parameter_node = _add_name_value_pair(self.graph, uri,
                                                  ALPACA.hasParameter,
                                                  name, value)
            if ontology_info:
                self._add_ontology_information(parameter_node,
                                               ontology_info, 'arguments',
                                               name)
        return uri

    # Entity methods
    @classmethod
    def _get_entity_value_datatype(cls, info):
        value = info.value
        if value is None:
            return None

        # Check if builtin type or NumPy dtype
        value_class = value.__class__ if not isinstance(value, np.number) \
            else value.dtype.type
        if value_class in cls.XSD_TYPES:
            return cls.XSD_TYPES[value_class]

        # Check if object is include in the `store_values` setting.
        # In this case, they are always stored as strings
        obj_type = info.type
        if obj_type in _ALPACA_SETTINGS['store_values']:
            return XSD.string

        for possible_type in (numbers.Integral, numbers.Real, numbers.Complex):
            if issubclass(value_class, possible_type):
                return cls.XSD_TYPES[possible_type]

        # Type not found
        return None

    def _add_DataObjectEntity(self, info):
        # Adds a DataObjectEntity from the Alpaca PROV model
        # If the entity already exists, skip it
        uri = URIRef(data_object_identifier(info, self._authority))

        if uri in self._entity_uris:
            return uri

        self.graph.add((uri, RDF.type, ALPACA.DataObjectEntity))
        self.graph.add((uri, ALPACA.hashSource, Literal(info.hash_method)))

        value_datatype = self._get_entity_value_datatype(info)
        if value_datatype:
            self.graph.add((uri, PROV.value,
                            Literal(info.value, datatype=value_datatype)))

        ontology_info = ONTOLOGY_INFORMATION.get(info.type, None)
        if ontology_info:
            self._add_ontology_information(uri, ontology_info, 'data_object')

        self._add_entity_metadata(uri, info, ontology_info)
        self._entity_uris.add(uri)
        return uri

    def _add_FileEntity(self, info):
        # Adds a FileEntity from the Alpaca PROV model
        uri = URIRef(file_identifier(info, self._authority))
        self.graph.add((uri, RDF.type, ALPACA.FileEntity))
        self.graph.add((uri, ALPACA.filePath,
                        Literal(info.path, datatype=XSD.string)))
        return uri

    def _add_entity_metadata(self, uri, info, ontology_info=None):
        # Add data object metadata (attributes, annotations) to the entities,
        # using properties from the Alpaca PROV model
        package_name = info.type.split(".")[0]
        metadata = info.details

        if package_name in self._metadata_plugins:
            # Handle objects like Neo objects (i.e., to avoid dumping all the
            # information in collections such as `segments` or `events`)
            metadata_nodes = self._metadata_plugins[package_name](
                self.graph, uri, metadata)

            # Process metadata nodes of the object, if ontology information
            # defined
            if ontology_info:
                for metadata_type, elements in metadata_nodes.items():
                    for element, node in elements.items():
                        self._add_ontology_information(node, ontology_info,
                                                       metadata_type, element)
        else:
            # Add metadata using default handling, i.e., all attributes
            for name, value in metadata.items():
                # Make sure that types such as list and Quantity are handled
                value = _ensure_type(value)

                blank_node = _add_name_value_pair(self.graph, uri=uri,
                    predicate=ALPACA.hasAttribute, name=name, value=value)

                if ontology_info:
                    self._add_ontology_information(blank_node, ontology_info,
                                                   'attributes', name)

    def _add_membership(self, container, child, params):
        # Add membership relationships according to the standard PROV model
        # and properties specific to the Alpaca PROV model
        predicates = {
            'name': ALPACA.fromAttribute,
            'index': ALPACA.containerIndex,
            'slice': ALPACA.containerSlice,
        }

        for name, value in params.items():
            predicate = predicates[name]
            self.graph.add((child, predicate, Literal(value)))
        self.graph.add((container, PROV.hadMember, child))

    def _create_entity(self, info):
        # Create an Alpaca PROV Entity based on DataObject/File information
        if isinstance(info, DataObject):
            return self._add_DataObjectEntity(info)
        elif isinstance(info, File):
            return self._add_FileEntity(info)
        raise ValueError("Invalid entity!")

    # Interface methods

    def _add_function_execution(self, execution, script_agent, script_info,
                                session_id):
        # Add one `FunctionExecution` record to the file, and generate all the
        # provenance semantic relationships

        def _is_membership(function_info):
            name = function_info.name
            return name in ("attribute", "subscript")

        function_info = execution.function
        if _is_membership(function_info):
            # attributes and subscripting operations
            container = execution.input[0]
            child = execution.output[0]
            container_entity = self._create_entity(container)
            if PROV.wasAttributedTo not in \
                    self.graph.predicates(container_entity, script_agent):
                self._wasAttributedTo(container_entity, script_agent)
            child_entity = self._create_entity(child)
            self._add_membership(container_entity, child_entity,
                                 execution.params)
        else:
            # This is a function execution. Add Function activity
            cur_function = self._add_Function(function_info)

            # ID to identify ontology annotations
            info_id = _get_function_name(function_info)
            ontology_info = ONTOLOGY_INFORMATION.get(info_id)

            # Get the FunctionExecution node with function parameters and
            # other provenance info
            cur_activity = self._add_FunctionExecution(
                script_info=script_info, session_id=session_id,
                execution_id=execution.execution_id,
                function_info=function_info, params=execution.params,
                execution_order=execution.order,
                code_statement=execution.code_statement,
                start=execution.time_stamp_start,
                end=execution.time_stamp_end,
                function=cur_function, ontology_info=ontology_info
            )

            # Add all the inputs as entities, and create a `used` association
            # with the activity. URNs differ when the input is a file or
            # Python object.
            input_entities = []
            for key, value in execution.input.items():
                cur_entities = []
                has_input_uri = ontology_info and \
                                bool(ontology_info.get_uri('arguments', key))

                if isinstance(value, Container):
                    # If this is a Container, several objects are inside.
                    for element in value.elements:
                        cur_entities.append(self._create_entity(element))
                else:
                    cur_entities.append(self._create_entity(value))

                input_entities.extend(cur_entities)

                for cur_entity in cur_entities:
                    self._used(activity=cur_activity, entity=cur_entity)
                    self._wasAttributedTo(entity=cur_entity,
                                          agent=script_agent)
                    if has_input_uri:
                        self._add_ontology_information(cur_entity,
                                                       ontology_info,
                                                       'arguments', key)

            # Add all the outputs as entities, and create the `wasGenerated`
            # relationship.
            output_entities = []
            for key, value in execution.output.items():
                cur_entity = self._create_entity(value)
                output_entities.append(cur_entity)
                self._wasGeneratedBy(entity=cur_entity, activity=cur_activity)
                self._wasAttributedTo(entity=cur_entity, agent=script_agent)
                if ontology_info:
                    self._add_ontology_information(cur_entity, ontology_info,
                                                   'returns', element=key)

            # Iterate over the input/output pairs to add the `wasDerived`
            # relationship
            for input_entity, output_entity in \
                    product(input_entities, output_entities):
                self._wasDerivedFrom(used_entity=input_entity,
                                     generated_entity=output_entity)

            # Associate the activity to the script
            self._wasAssociatedWith(activity=cur_activity, agent=script_agent)

    def _add_annotations_for_container_outputs(self):
        # For functions that the Provenance decorator identified elements
        # inside returned containers, the elements linked by `prov:hasMember`
        # functions need to be annotated. The list of functions is already
        # stored in a search list. Iterate over the nodes of the function
        # and annotate the correct level of membership

        for info_id, levels in self._container_output_functions.items():

            # Initialize a container to store the URIs of elements of each
            # output level starting from the function. Since the capture can
            # ignore root levels, and to avoid recursion, we will map
            # container entities up to the maximum possible level taken from
            # the 'returns' annotations. Later, we take the annotations
            # starting from the deepest level.

            int_levels = list(map(lambda x: len(x), levels))
            max_level = max(int_levels)
            elements_by_level = {level: [] for level in range(max_level)}

            # Fetch information on the function, to identify nodes in the graph
            ontology_info = ONTOLOGY_INFORMATION[info_id]
            function_type = ontology_info.get_uri('function')
            executions = self.graph.subjects(RDF.type, function_type)

            # For every execution, get the output nodes
            # This is the first level
            for execution in executions:
                elements_by_level[0].extend(
                    self.graph.subjects(PROV.wasGeneratedBy, execution))

            # Traverse the remaining levels
            for level in range(1, max_level):
                for element in chain(elements_by_level[level-1]):
                    members = self.graph.objects(element, PROV.hadMember)
                    elements_by_level[level].extend(members)

            # Go from the deepest annotation level, annotating the deepest
            # node level with elements
            level_depth = max_level - 1
            level_str = '*' * max_level
            obj_uri = ontology_info.get_uri('returns', level_str)

            while level_depth >= 0:
                if obj_uri:
                    has_elements = False
                    for element in chain(elements_by_level[level_depth]):
                        has_elements = True
                        self.graph.add((element, RDF.type, obj_uri))
                else:
                    # No annotation requested for this level
                    # Consider the level traversed
                    has_elements = True

                if has_elements:
                    # Fetch annotation information for the parent level
                    level_str = '*' * (len(level_str) - 1)
                    obj_uri = ontology_info.get_uri('returns', level_str)

                # If no element found, keep the annotation level, but
                # try to annotate the elements of an upper node level
                level_depth -= 1

    def add_history(self, script_info, session_id, history,
                    show_progress=False):
        """
        Adds a history of `FunctionExecution` records captured by Alpaca to an
        RDF document using the Alpaca PROV ontology. The script is added as
        a `ScriptAgent` agent.

        Parameters
        ----------
        script_info : alpaca_types.File
            Named tuple with the information on the script being tracked
            (hash and file path).
        session_id : str
            Unique identifier for this script execution.
        history : list of FunctionExecution
            Provenance history to be serialized as RDF using PROV.
        show_progress : bool, optional
            If True, show the progress of the provenance history serialization.
            Default: False
        """
        script_agent = self._add_ScriptAgent(script_info, session_id)
        for execution in tqdm(history, desc="Serializing provenance history",
                              disable=not show_progress):
            self._add_function_execution(execution, script_agent, script_info,
                                         session_id)
        self._add_annotations_for_container_outputs()

    def read_records(self, file_name, file_format='turtle'):
        """
        Reads PROV data that was previously serialized as RDF.

        Parameters
        ----------
        file_name : str or Path-like
            Location of the file with PROV data to be read.
        file_format : {'json-ld', 'n3', 'nt', 'turtle', 'xml', 'ttl', 'rdf', 'json'}
            Format used to serialize the file that is being read. If None, the
            format will be inferred from the extension. The formats are
            the ones accepted by RDFLib. Some shortucts are defined for common
            file extensions:

            * 'ttl': Turtle
            * 'rdf': RDF-XML
            * 'json': JSON-LD

        Raises
        ------
        ValueError
            If `file_format` is None and `file_name` has no extension to infer
            the format, if it could not be inferred, or if the format is
            invalid.
        """
        if file_format is None:
            file_format = _get_prov_file_format(file_name)

        if file_format is None:
            raise ValueError("Could not infer serialization format. Please,"
                             "provide it explicitly using `file_format`.")

        if file_format not in ['json-ld', 'n3', 'nt', 'turtle', 'xml']:
            raise ValueError("Unsupported serialization format")

        with open(file_name, "r") as source:
            self.graph.parse(source, format=file_format)

    def serialize(self, file_name, file_format='turtle'):
        """
        Writes PROV data to a file or gets an in-memory string.

        Parameters
        ----------
        file_name : str or Path-like
            Location of the file with PROV data to be read.
        file_format : {'json-ld', 'n3', 'nt', 'hext', 'pretty-xml', 'trig', 'turtle', 'longturtle', 'xml'}
            Format used in the file that is being read. The format strings are
            the ones supported by RDFLib.
            If None, the format will be inferred from the extension.
            Default: 'turtle'

        """
        return self.graph.serialize(file_name, format=file_format)
