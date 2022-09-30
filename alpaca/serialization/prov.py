"""
This module implements functionality to serialize the provenance track using
the W3C Provenance Data Model (PROV). A derived model is defined in an
ontology and is used to serialize the provenance information captured by
Alpaca.
"""

from itertools import product

from rdflib import Graph, URIRef, BNode, Literal
from rdflib.namespace import RDF, PROV, XSD

from alpaca.ontology import ALPACA
from alpaca.serialization.identifiers import (data_object_identifier,
                                              file_identifier,
                                              function_identifier,
                                              script_identifier,
                                              execution_identifier)
from alpaca.serialization.converters import _ensure_type
from alpaca.serialization.neo import _neo_object_metadata

from alpaca.utils.files import _get_file_format
from alpaca.types import ObjectInfo, FileInfo, VarArgs


def _add_name_value_pair(graph, uri, predicate, name, value):
    # Add a relationship defined by `predicate` using a blank node as object.
    # The object will be of type `alpaca:NameValuePair`.
    blank_node = BNode()
    graph.add((uri, predicate, blank_node))
    graph.add((blank_node, RDF.type, ALPACA.NameValuePair))
    graph.add((blank_node, ALPACA.pairName, Literal(name)))
    graph.add((blank_node, ALPACA.pairValue, Literal(value)))


class AlpacaProvDocument(object):

    def __init__(self):
        self.graph = Graph()
        self.graph.namespace_manager.bind('alpaca', ALPACA)

        # For packages (e.g., Neo) that require special handling of metadata,
        # when adding to the PROV records. Plugins are external functions
        # that take the graph, the object URI, and the metadata dict as
        # parameters.
        self._metadata_plugins = {
            'neo': _neo_object_metadata
        }

    # PROV relationships methods

    def _wasAttributedTo(self, activity, agent):
        self.graph.add((activity, PROV.wasAttributedTo, agent))

    def _qualifiedGeneration(self, entity, activity, time, function_execution):
        generation = BNode()
        self.graph.add((generation, RDF.type, ALPACA.DataGeneration))
        self.graph.add((generation, ALPACA.fromFunctionExecution,
                        function_execution))
        self.graph.add((generation, PROV.atTime,
                        Literal(time, datatype=XSD.dateTime)))
        self.graph.add((generation, PROV.activity, activity))
        self.graph.add((entity, PROV.qualifiedGeneration, generation))

    def _qualifiedUsage(self, activity, entity, time, function_execution):
        usage = BNode()
        self.graph.add((usage, RDF.type, ALPACA.DataUsage))
        self.graph.add((usage, ALPACA.byFunctionExecution,
                        function_execution))
        self.graph.add((usage, PROV.atTime, Literal(time,
                                                    datatype=XSD.dateTime)))
        self.graph.add((usage, PROV.entity, entity))
        self.graph.add((activity, PROV.qualifiedUsage, usage))

    def _wasDerivedFrom(self, used_entity, generated_entity):
        self.graph.add((generated_entity, PROV.wasDerivedFrom, used_entity))

    # Agent methods

    def _add_ScriptAgent(self, script_info, session_id):
        uri = URIRef(script_identifier(script_info, session_id))
        self.graph.add((uri, RDF.type, ALPACA.ScriptAgent))
        return uri

    # Activity methods

    def _add_Function(self, info):
        uri = URIRef(function_identifier(info))
        self.graph.add((uri, RDF.type, ALPACA.Function))
        return uri

    def _add_FunctionExecution(self, script_info, session_id, execution_id,
                               params, execution_order, code_statement):
        uri = URIRef(execution_identifier(
            script_info, session_id, execution_id))
        self.graph.add((uri, RDF.type, ALPACA.FunctionExecution))
        self.graph.add((uri, ALPACA.codeStatement, Literal(code_statement)))
        self.graph.add((uri, ALPACA.executionOrder,
                        Literal(execution_order, datatype=XSD.integer)))

        for name, value in params.items():
            value = _ensure_type(value)
            _add_name_value_pair(self.graph, uri, ALPACA.hasParameter,
                                 name, value)
        return uri

    # Entity methods

    def _add_DataObjectEntity(self, info):
        # Adds a DataObjectEntity from the Alpaca PROV model
        # If the entity already exists, skip it
        uri = URIRef(data_object_identifier(info))

        if uri in self.graph.subjects(RDF.type, ALPACA.DataObjectEntity):
            return uri
        self.graph.add((uri, RDF.type, ALPACA.DataObjectEntity))
        self._add_entity_metadata(uri, info)
        return uri

    def _add_FileEntity(self, info):
        # Adds a FileEntity from the Alpaca PROV model
        uri = URIRef(file_identifier(info))
        self.graph.add((uri, RDF.type, ALPACA.FileEntity))
        self.graph.add((uri, ALPACA.filePath,
                        Literal(info.path, datatype=XSD.string)))
        return uri

    def _add_entity_metadata(self, uri, info):
        # Add data object metadata (attributes, annotations) to the entities,
        # using properties from the Alpaca PROV model
        package_name = info.type.split(".")[0]
        metadata = info.details

        if package_name in self._metadata_plugins:
            # Handle Neo objects, to avoid dumping all the information
            # in collections such as `segments` or `events`
            self._metadata_plugins[package_name](self.graph, uri, metadata)
        else:
            # Add metadata using default handling, i.e., all attributes
            for name, value in metadata.items():
                # Make sure that types such as list and Quantity are handled
                value = _ensure_type(value)

                _add_name_value_pair(self.graph, uri=uri,
                                     predicate=ALPACA.hasAttribute,
                                     name=name,
                                     value=value)

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
        # Create an Alpaca PROV Entity based on ObjectInfo/FileInfo information
        if isinstance(info, ObjectInfo):
            return self._add_DataObjectEntity(info)
        elif isinstance(info, FileInfo):
            return self._add_FileEntity(info)
        raise ValueError("Invalid entity!")

    # Interface methods

    def _add_analysis_step(self, step, script_agent, script_info, session_id):
        # Add one `AnalysisStep` record to the file, generate all the
        # provenance semantic relationships

        def _is_membership(function_info):
            name = function_info.name
            return name in ("attribute", "subscript")

        function_info = step.function
        if _is_membership(function_info):
            # attributes and subscripting operations
            container = step.input[0]
            child = step.output[0]
            container_entity = self._create_entity(container)
            child_entity = self._create_entity(child)
            self._add_membership(container_entity, child_entity, step.params)
        else:
            # This is a function execution. Add Function activity
            cur_activity = self._add_Function(function_info)

            # Get the FunctionExecution node with function parameters
            function_execution = self._add_FunctionExecution(
                script_info=script_info, session_id=session_id,
                execution_id=step.execution_id,
                params=step.params, execution_order=step.order,
                code_statement=step.code_statement)

            step_time = step.time_stamp_end

            # Add all the inputs as entities, and create a `used` association
            # with the activity. URNs differ when the input is a file or
            # Python object.
            # This is a qualified relationship, as the attributes are stored
            # together with the timestamp
            input_entities = []
            for key, value in step.input.items():
                cur_entities = []

                if isinstance(value, VarArgs):
                    # If this is a VarArgs, several objects are inside.
                    for var_arg in value.args:
                        cur_entities.append(self._create_entity(var_arg))
                else:
                    cur_entities.append(self._create_entity(value))

                input_entities.extend(cur_entities)

                for cur_entity in cur_entities:
                    self._qualifiedUsage(activity=cur_activity,
                                         entity=cur_entity,
                                         time=step_time,
                                         function_execution=function_execution)

            # Add all the outputs as entities, and create the `wasGenerated`
            # relationship. This is a qualified relationship, as the attributes
            # will be stored together with the timestamp.
            output_entities = []
            for key, value in step.output.items():
                cur_entity = self._create_entity(value)
                output_entities.append(cur_entity)
                self._qualifiedGeneration(entity=cur_entity,
                                          activity=cur_activity,
                                          time=step_time,
                                          function_execution=
                                              function_execution)

            # Iterate over the input/output pairs to add the `wasDerived`
            # relationship
            for input_entity, output_entity in \
                    product(input_entities, output_entities):
                self._wasDerivedFrom(used_entity=input_entity,
                                     generated_entity=output_entity)

            # Attribute the activity to the script
            self._wasAttributedTo(activity=cur_activity, agent=script_agent)

    def add_analysis_steps(self, script_info, session_id, analysis_steps):
        """
        Adds a history of `AnalysisStep` records captured by Alpaca to a PROV
        document.

        Parameters
        ----------
        script_info : FileInfo
            Information on the script being tracked (hash and file path).
        session_id : str
            Unique identifier for this script execution.
        analysis_steps : list of AnalysisStep
            Provenance history to be serialized as PROV.
        """
        script_agent = self._add_ScriptAgent(script_info, session_id)
        for step in analysis_steps:
            self._add_analysis_step(step, script_agent, script_info,
                                    session_id)

    def read_records(self, file_name, file_format='ttl'):
        """
        Reads PROV data that was previously serialized.

        Parameters
        ----------
        file_name : str or path-like
            Location of the file with PROV data to be read.
        file_format : {'json', 'rdf', 'ttl', 'xml'}
            Format used in the file that is being read.
            Turtle files (*.ttl) are treated as RDF files.
            If None, the format will be inferred from the extension.
            Default: 'ttl'

        Raises
        ------
        ValueError
            If `file_format` is None and `file_name` has no extension to infer
            the format.
            If `file_format` is not 'rdf', 'ttl', 'json', or 'xml'.
        """
        if file_format is None:
            file_format = _get_file_format(file_name)

        if file_format not in ['rdf', 'json', 'xml', 'ttl']:
            raise ValueError("Unsupported serialization format")

        with open(file_name, "r") as source:
            self.graph.parse(source, format=file_format)

    def serialize(self, file_name, format='turtle'):
        self.graph.serialize(file_name, format=format)
