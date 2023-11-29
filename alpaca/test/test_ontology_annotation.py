import unittest
import io
from rdflib import Literal, URIRef, Namespace, Graph, RDF, PROV

from alpaca import activate, deactivate, Provenance, save_provenance
from alpaca.ontology.annotation import (_OntologyInformation,
                                        ONTOLOGY_INFORMATION)
from alpaca.ontology import ALPACA

from collections import Counter

# Ontology namespace definition used for the tests
EXAMPLE_NS = {'ontology': "http://example.org/ontology#"}


##############################
# Test objects to be annotated
##############################

class InputObject:
    __ontology__ = {
        "data_object": "ontology:InputObject",
        "namespaces": EXAMPLE_NS}


class OutputObject:
    __ontology__ = {
        "data_object": "ontology:OutputObject",
        "attributes": {'name': "ontology:Attribute"},
        "namespaces": EXAMPLE_NS}

    def __init__(self, name, channel):
        self.name = name
        self.channel = channel


class InputObjectURI:
    __ontology__ = {"data_object": "<http://purl.org/ontology#InputObject>"}


#######################################################
# Test functions to be annotated and provenance tracked
#######################################################

@Provenance(inputs=['input'])
def process(input, param_1):
    return OutputObject("SpikeTrain#1", 45)

process.__wrapped__.__ontology__ = {
    "function": "ontology:ProcessFunction",
    "namespaces": EXAMPLE_NS,
    "arguments": {'param_1': "ontology:Parameter"},
    "returns": {0: "ontology:ProcessedData"}
}


@Provenance(inputs=['input'])
def process_one_and_process_two(input, param_1):
    return OutputObject("SpikeTrain#1", 45)

process_one_and_process_two.__wrapped__.__ontology__ = {
    "function": ["ontology:Process1Function", "ontology:Process2Function"],
    "namespaces": EXAMPLE_NS,
    "arguments": {'param_1': "ontology:Parameter"},
    "returns": {0: "ontology:ProcessedData"}
}


@Provenance(inputs=['input'])
def process_multiple(input, param_1):
    return "not_annotated", OutputObject("SpikeTrain#2", 34)

process_multiple.__wrapped__.__ontology__ = {
    "function": "ontology:ProcessFunctionMultiple",
    "namespaces": EXAMPLE_NS,
    "arguments": {'param_1': "ontology:Parameter"},
    "returns": {1: "ontology:ProcessedDataMultiple"}
}


@Provenance(inputs=[], container_output=True)
def process_container_output():
    return list(range(3))

process_container_output.__wrapped__.__ontology__ = {
    "function": "ontology:ProcessContainerOutput",
    "namespaces": EXAMPLE_NS,
    "returns": {'*': "ontology:ProcessedContainerOutput"}
}


@Provenance(inputs=[], container_output=1)
def process_multiple_container_output():
    return [list(range(i, i + 3)) for i in range(0, 7, 3)]

process_multiple_container_output.__wrapped__.__ontology__ = {
    "function": "ontology:ProcessMultipleContainerOutput",
    "namespaces": EXAMPLE_NS,
    "returns": {'***': "ontology:ProcessedMultipleContainerOutput"}
}


@Provenance(inputs=[], container_output=1)
def process_multiple_container_output_multiple_annotations():
    return [list(range(i, i + 3)) for i in range(0, 4, 3)]

process_multiple_container_output_multiple_annotations.__wrapped__.__ontology__ = {
    "function": "ontology:ProcessMultipleContainerOutputMultipleAnnotations",
    "namespaces": EXAMPLE_NS,
    "returns": {
        '**': "ontology:ProcessedMultipleContainerOutputLevel1",
        '***': "ontology:ProcessedMultipleContainerOutputLevel2"}
}


@Provenance(inputs=[], container_output=1)
def process_multiple_container_output_multiple_annotations_root():
    return [list(range(i, i + 3)) for i in range(0, 4, 3)]

process_multiple_container_output_multiple_annotations_root.__wrapped__.__ontology__ = {
    "function": "ontology:ProcessMultipleContainerOutputMultipleAnnotationsRoot",
    "namespaces": EXAMPLE_NS,
    "returns": {
        '*': "ontology:ProcessedMultipleContainerOutputLevel0",
        '**': "ontology:ProcessedMultipleContainerOutputLevel1",
        '***': "ontology:ProcessedMultipleContainerOutputLevel2"}
}


@Provenance(inputs=[], container_output=(1, 1))
def process_multiple_container_output_multiple_annotations_range():
    return [list(range(i, i + 3)) for i in range(0, 4, 3)]

process_multiple_container_output_multiple_annotations_range.__wrapped__.__ontology__ = {
    "function": "ontology:ProcessMultipleContainerOutputMultipleAnnotationsRange",
    "namespaces": EXAMPLE_NS,
    "returns": {
        '*': "ontology:ProcessedMultipleContainerOutputLevel0",
        '**': "ontology:ProcessedMultipleContainerOutputLevel1",
        '***': "ontology:ProcessedMultipleContainerOutputLevel2"}
}


@Provenance(inputs=['input'])
def process_input_annotation(input, param):
    return input + 2

process_input_annotation.__wrapped__.__ontology__ = {
    "function": "ontology:ProcessInputAnnotation",
    "namespaces": EXAMPLE_NS,
    "arguments": {'input': "ontology:Input", 'param': "ontology:Param"}
}


@Provenance(inputs=['input'], container_input=['input_list'])
def process_container_input_annotation(input, input_list, param):
    return [i + input for i in input_list]

process_container_input_annotation.__wrapped__.__ontology__ = {
    "function": "ontology:ProcessContainerInputAnnotation",
    "namespaces": EXAMPLE_NS,
    "arguments": {'input': "ontology:Input",
                  'input_list': "ontology:ContainerElementInput",
                  'param': "ontology:Param"}
}


@Provenance(inputs=['input'])
def process_no_annotations(input):
    return input + 2


############
# Unit tests
############

class OntologyAnnotationTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create rdflib Namespace for tests
        cls.ONTOLOGY = Namespace(EXAMPLE_NS['ontology'])

    def setUp(self):
        _OntologyInformation.namespaces.clear()
        ONTOLOGY_INFORMATION.clear()

    def test_redefine_namespaces(self):
        obj = InputObject()
        self.assertDictEqual(_OntologyInformation.namespaces, {})
        info = _OntologyInformation(obj)

        # At this point, the class should be updated with the 'ontology'
        # namespace
        with self.assertRaises(ValueError):
            info.add_namespace('ontology', "http://purl.org/ontology")

        info.add_namespace('purl_ontology', "http://purl.org/ontology")
        self.assertEqual(len(info.namespaces), 2)

        self.assertEqual(info.namespaces['ontology'], self.ONTOLOGY)
        self.assertEqual(info.namespaces['purl_ontology'],
                         Namespace("http://purl.org/ontology"))

    def test_annotation_object_input_uri(self):
        obj = InputObjectURI()
        self.assertIsNotNone(
            _OntologyInformation.get_ontology_information(obj))
        info = _OntologyInformation(obj)
        self.assertEqual(
            info.get_uri("data_object"),
            URIRef("http://purl.org/ontology#InputObject"))

        # Namespaces included in representation as this is a class attribute
        self.assertEqual(
            str(info),
            "OntologyInformation(data_object='"
            "<http://purl.org/ontology#InputObject>', namespaces={})"
        )

    def test_annotation_object_input(self):
        obj = InputObject()
        self.assertIsNotNone(
            _OntologyInformation.get_ontology_information(obj))
        info = _OntologyInformation(obj)
        self.assertEqual(
            info.get_uri("data_object"),
            URIRef("http://example.org/ontology#InputObject"))
        self.assertEqual(
            str(info),
            "OntologyInformation(data_object='ontology:InputObject', "
            f"namespaces={{'ontology': {repr(self.ONTOLOGY)}}})"
        )

    def test_annotation_object_output(self):
        obj = OutputObject("test", 45)
        self.assertIsNotNone(
            _OntologyInformation.get_ontology_information(obj))
        info = _OntologyInformation(obj)
        self.assertEqual(
            info.get_uri("data_object"),
            URIRef("http://example.org/ontology#OutputObject"))
        self.assertEqual(
            info.get_uri("attributes", "name"),
            URIRef("http://example.org/ontology#Attribute"))
        self.assertEqual(
            str(info),
            "OntologyInformation(data_object='ontology:OutputObject', "
            "attributes={'name': 'ontology:Attribute'}, "
            f"namespaces={{'ontology': {repr(self.ONTOLOGY)}}})"
        )

    def test_annotation_function(self):
        self.assertIsNotNone(
            _OntologyInformation.get_ontology_information(process))
        info = _OntologyInformation(process)
        self.assertEqual(
            info.get_uri("function"),
            URIRef("http://example.org/ontology#ProcessFunction"))
        self.assertEqual(
            info.get_uri("arguments", "param_1"),
            URIRef("http://example.org/ontology#Parameter"))
        self.assertEqual(
            info.get_uri("returns", 0),
            URIRef("http://example.org/ontology#ProcessedData"))
        self.assertEqual(
            str(info),
            "OntologyInformation(function='ontology:ProcessFunction', "
            "arguments={'param_1': 'ontology:Parameter'}, "
            f"namespaces={{'ontology': {repr(self.ONTOLOGY)}}}, "
            "returns={0: 'ontology:ProcessedData'})"
        )

    def test_annotation_function_multiple_annotations(self):
        self.assertIsNotNone(
            _OntologyInformation.get_ontology_information(
                process_one_and_process_two))
        info = _OntologyInformation(process_one_and_process_two)
        self.assertListEqual(
            info.get_uri("function"),
            [URIRef("http://example.org/ontology#Process1Function"),
             URIRef("http://example.org/ontology#Process2Function")])
        self.assertEqual(
            info.get_uri("arguments", "param_1"),
            URIRef("http://example.org/ontology#Parameter"))
        self.assertEqual(
            info.get_uri("returns", 0),
            URIRef("http://example.org/ontology#ProcessedData"))
        self.assertEqual(
            str(info),
            "OntologyInformation(function='['ontology:Process1Function', "
            "'ontology:Process2Function']', "
            "arguments={'param_1': 'ontology:Parameter'}, "
            f"namespaces={{'ontology': {repr(self.ONTOLOGY)}}}, "
            "returns={0: 'ontology:ProcessedData'})")

    def test_annotation_function_multiple(self):
        self.assertIsNotNone(
            _OntologyInformation.get_ontology_information(process_multiple))
        info = _OntologyInformation(process_multiple)
        self.assertEqual(
            info.get_uri("function"),
            URIRef("http://example.org/ontology#ProcessFunctionMultiple"))
        self.assertEqual(
            info.get_uri("arguments", "param_1"),
            URIRef("http://example.org/ontology#Parameter"))
        self.assertEqual(
            info.get_uri("returns", 1),
            URIRef("http://example.org/ontology#ProcessedDataMultiple"))
        self.assertEqual(
            str(info),
            "OntologyInformation(function='ontology:ProcessFunctionMultiple', "
            "arguments={'param_1': 'ontology:Parameter'}, "
            f"namespaces={{'ontology': {repr(self.ONTOLOGY)}}}, "
            "returns={1: 'ontology:ProcessedDataMultiple'})"
        )

    def test_invalid_object_annotations(self):
        obj = InputObject()
        info = _OntologyInformation(obj)
        self.assertIsNone(info.get_uri("attributes", "name"))
        self.assertIsNone(info.get_uri("attributes", "channel"))
        self.assertIsNone(info.get_uri("non_existent"))
        self.assertIsNone(info.get_uri("non_existent", "test"))

        output_obj = OutputObject("test", 45)
        output_info = _OntologyInformation(output_obj)
        self.assertIsNotNone(output_info.get_uri("attributes", "name"))
        self.assertIsNone(output_info.get_uri("attributes", "channel"))
        self.assertIsNone(output_info.get_uri("non_existent"))
        self.assertIsNone(output_info.get_uri("non_existent", "test"))

    def test_namespaces(self):
        input_obj = InputObject()
        output_obj = OutputObject("test", 45)

        input_info = _OntologyInformation(input_obj)
        output_info = _OntologyInformation(output_obj)
        function_info = _OntologyInformation(process)

        for info in (input_info, output_info, function_info):
            self.assertEqual(info.namespaces['ontology'], self.ONTOLOGY)
            self.assertTupleEqual(tuple(info.namespaces.keys()), ('ontology',))

    def test_provenance_no_annotation(self):
        activate(clear=True)
        result = process_no_annotations(5)
        deactivate()

        prov_data = save_provenance()

        # Read PROV information as RDF
        prov_graph = Graph()
        with io.StringIO(prov_data) as data_stream:
            prov_graph.parse(data_stream, format='turtle')

        # Check that no other annotations are present
        execution_uri = list(
            prov_graph.subjects(RDF.type, ALPACA.FunctionExecution))[0]
        types = list(prov_graph.objects(execution_uri, RDF.type))
        self.assertListEqual(types, [ALPACA.FunctionExecution])

    def test_provenance_annotation(self):
        activate(clear=True)
        input_object = InputObject()
        output_object = process(input_object, 34)
        deactivate()

        prov_data = save_provenance()

        # Read PROV information as RDF
        prov_graph = Graph()
        with io.StringIO(prov_data) as data_stream:
            prov_graph.parse(data_stream, format='turtle')

        # Check that the annotations exist (1 per class is expected)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.Parameter)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessFunction)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessedData)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.InputObject)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.OutputObject)))
            ), 1)

        # FunctionExecution is ProcessFunction
        execution_uri = list(
            prov_graph.subjects(RDF.type, ALPACA.FunctionExecution))[0]
        self.assertTrue((execution_uri,
                         RDF.type,
                         self.ONTOLOGY.ProcessFunction) in prov_graph)

        # Check parameter name
        parameter_node = list(
            prov_graph.subjects(RDF.type, self.ONTOLOGY.Parameter))[0]
        self.assertTrue((parameter_node,
                         ALPACA.pairName, Literal("param_1")) in prov_graph)
        self.assertTrue((parameter_node,
                         ALPACA.pairValue, Literal(34)) in prov_graph)

        # Check returned value
        output_node = list(
            prov_graph.subjects(RDF.type, self.ONTOLOGY.ProcessedData))[0]
        self.assertTrue((output_node,
                         PROV.wasGeneratedBy, execution_uri) in prov_graph)
        self.assertTrue((output_node,
                         RDF.type, ALPACA.DataObjectEntity) in prov_graph)
        self.assertTrue((output_node,
                         RDF.type, self.ONTOLOGY.OutputObject) in prov_graph)

        # Check attributes of returned value
        expected_attributes = {
            'name': "SpikeTrain#1",
            'channel': 45,
        }
        for attribute in prov_graph.objects(output_node, ALPACA.hasAttribute):
            name = prov_graph.value(attribute, ALPACA.pairName).toPython()
            value = prov_graph.value(attribute, ALPACA.pairValue).toPython()
            self.assertEqual(value, expected_attributes[name])

            # Check if attribute annotation is present for `name`
            if name == 'name':
                self.assertTrue((attribute, RDF.type, self.ONTOLOGY.Attribute)
                                in prov_graph)

        # Check input value
        input_node = list(
            prov_graph.subjects(RDF.type, self.ONTOLOGY.InputObject))[0]
        self.assertTrue((execution_uri, PROV.used, input_node) in prov_graph)
        self.assertTrue((input_node,
                         RDF.type, ALPACA.DataObjectEntity) in prov_graph)
        self.assertTrue((output_node,
                         PROV.wasDerivedFrom, input_node) in prov_graph)

    def test_provenance_multiple_annotations(self):
        activate(clear=True)
        input_object = InputObject()
        output_object = process_one_and_process_two(input_object, 34)
        deactivate()

        prov_data = save_provenance()

        # Read PROV information as RDF
        prov_graph = Graph()
        with io.StringIO(prov_data) as data_stream:
            prov_graph.parse(data_stream, format='turtle')

        # Check that the annotations exist (1 per class is expected)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.Parameter)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.Process1Function)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.Process2Function)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessedData)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.InputObject)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.OutputObject)))
            ), 1)

        # FunctionExecution is ProcessFunction
        execution_uri = list(
            prov_graph.subjects(RDF.type, ALPACA.FunctionExecution))[0]
        self.assertTrue((execution_uri,
                         RDF.type,
                         self.ONTOLOGY.Process1Function) in prov_graph)

        self.assertTrue((execution_uri,
                         RDF.type,
                         self.ONTOLOGY.Process2Function) in prov_graph)

        # Check parameter name
        parameter_node = list(
            prov_graph.subjects(RDF.type, self.ONTOLOGY.Parameter))[0]
        self.assertTrue((parameter_node,
                         ALPACA.pairName, Literal("param_1")) in prov_graph)
        self.assertTrue((parameter_node,
                         ALPACA.pairValue, Literal(34)) in prov_graph)

        # Check returned value
        output_node = list(
            prov_graph.subjects(RDF.type, self.ONTOLOGY.ProcessedData))[0]
        self.assertTrue((output_node,
                         PROV.wasGeneratedBy, execution_uri) in prov_graph)
        self.assertTrue((output_node,
                         RDF.type, ALPACA.DataObjectEntity) in prov_graph)
        self.assertTrue((output_node,
                         RDF.type, self.ONTOLOGY.OutputObject) in prov_graph)

        # Check attributes of returned value
        expected_attributes = {
            'name': "SpikeTrain#1",
            'channel': 45,
        }
        for attribute in prov_graph.objects(output_node, ALPACA.hasAttribute):
            name = prov_graph.value(attribute, ALPACA.pairName).toPython()
            value = prov_graph.value(attribute, ALPACA.pairValue).toPython()
            self.assertEqual(value, expected_attributes[name])

            # Check if attribute annotation is present for `name`
            if name == 'name':
                self.assertTrue((attribute, RDF.type, self.ONTOLOGY.Attribute)
                                in prov_graph)

        # Check input value
        input_node = list(
            prov_graph.subjects(RDF.type, self.ONTOLOGY.InputObject))[0]
        self.assertTrue((execution_uri, PROV.used, input_node) in prov_graph)
        self.assertTrue((input_node,
                         RDF.type, ALPACA.DataObjectEntity) in prov_graph)
        self.assertTrue((output_node,
                         PROV.wasDerivedFrom, input_node) in prov_graph)

    def test_provenance_annotation_multiple_returns(self):
        activate(clear=True)
        input_object = InputObject()
        name, output_object = process_multiple(input_object, 45)
        deactivate()

        prov_data = save_provenance()

        # Read PROV information as RDF
        prov_graph = Graph()
        with io.StringIO(prov_data) as data_stream:
            prov_graph.parse(data_stream, format='turtle')

        # Check that the annotations exist (1 per class is expected. None
        # are expected for the classes of `process`)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.Parameter)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessFunctionMultiple)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessedDataMultiple)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.InputObject)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.OutputObject)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessFunction)))
            ), 0)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessedData)))
            ), 0)

        # FunctionExecution is ProcessFunctionMultiple
        execution_uri = list(
            prov_graph.subjects(RDF.type, ALPACA.FunctionExecution))[0]
        self.assertTrue((execution_uri, RDF.type,
                         self.ONTOLOGY.ProcessFunctionMultiple) in prov_graph)

        # Check parameter name
        parameter_node = list(
            prov_graph.subjects(RDF.type, self.ONTOLOGY.Parameter))[0]
        self.assertTrue((parameter_node,
                         ALPACA.pairName, Literal("param_1")) in prov_graph)
        self.assertTrue((parameter_node,
                         ALPACA.pairValue, Literal(45)) in prov_graph)

        # Check returned value
        output_node = list(
            prov_graph.subjects(RDF.type,
                                self.ONTOLOGY.ProcessedDataMultiple))[0]
        self.assertTrue((output_node,
                         PROV.wasGeneratedBy, execution_uri) in prov_graph)
        self.assertTrue((output_node,
                         RDF.type, ALPACA.DataObjectEntity) in prov_graph)
        self.assertTrue((output_node,
                         RDF.type, self.ONTOLOGY.OutputObject) in prov_graph)

        # Check attributes of returned value
        expected_attributes = {
            'name': "SpikeTrain#2",
            'channel': 34,
        }
        for attribute in prov_graph.objects(output_node, ALPACA.hasAttribute):
            name = prov_graph.value(attribute, ALPACA.pairName).toPython()
            value = prov_graph.value(attribute, ALPACA.pairValue).toPython()
            self.assertEqual(value, expected_attributes[name])

            # Check if attribute annotation is present for `name`
            if name == 'name':
                self.assertTrue((attribute, RDF.type, self.ONTOLOGY.Attribute)
                                in prov_graph)

        # Check input value
        input_node = list(
            prov_graph.subjects(RDF.type, self.ONTOLOGY.InputObject))[0]
        self.assertTrue((execution_uri,
                         PROV.used, input_node) in prov_graph)
        self.assertTrue((input_node,
                         RDF.type, ALPACA.DataObjectEntity) in prov_graph)
        self.assertTrue((output_node,
                         PROV.wasDerivedFrom, input_node) in prov_graph)

    def test_provenance_annotation_container_output(self):
        activate(clear=True)
        container = process_container_output()
        deactivate()

        prov_data = save_provenance()

        # Read PROV information as RDF
        prov_graph = Graph()
        with io.StringIO(prov_data) as data_stream:
            prov_graph.parse(data_stream, format='turtle')

        # Check that the annotations exist (1 per class is expected. None
        # are expected for the classes of `process`)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessContainerOutput)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessedContainerOutput)))
            ), 3)

        # FunctionExecution is ProcessContainerOutput
        execution_uri = list(
            prov_graph.subjects(RDF.type, ALPACA.FunctionExecution))[0]
        self.assertTrue((execution_uri, RDF.type,
                         self.ONTOLOGY.ProcessContainerOutput) in prov_graph)

        # Check returned values
        output_nodes = prov_graph.subjects(RDF.type,
                                self.ONTOLOGY.ProcessedContainerOutput)
        for output_node in output_nodes:
            self.assertTrue((output_node,
                             PROV.wasGeneratedBy, execution_uri) in prov_graph)
            self.assertTrue((output_node,
                             RDF.type, ALPACA.DataObjectEntity) in prov_graph)
            self.assertTrue((output_node,
                             RDF.type, self.ONTOLOGY.ProcessedContainerOutput)
                            in prov_graph)

    def test_provenance_annotation_container_multiple_output(self):
        activate(clear=True)
        container = process_multiple_container_output()
        deactivate()

        prov_data = save_provenance()

        # Read PROV information as RDF
        prov_graph = Graph()
        with io.StringIO(prov_data) as data_stream:
            prov_graph.parse(data_stream, format='turtle')

        # Check that the annotations exist
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessMultipleContainerOutput)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessedMultipleContainerOutput)))
            ), 9)

        # FunctionExecution is ProcessMultipleContainerOutput
        execution_uri = list(
            prov_graph.subjects(RDF.type, ALPACA.FunctionExecution))[0]
        self.assertTrue((execution_uri, RDF.type,
                         self.ONTOLOGY.ProcessMultipleContainerOutput) in prov_graph)

        # Check returned values
        output_nodes = prov_graph.subjects(RDF.type,
                                self.ONTOLOGY.ProcessedMultipleContainerOutput)
        for output_node in output_nodes:
            self.assertTrue((None, PROV.hadMember, output_node) in prov_graph)
            self.assertTrue((output_node,
                             RDF.type, ALPACA.DataObjectEntity) in prov_graph)
            self.assertTrue((output_node,
                             RDF.type, self.ONTOLOGY.ProcessedMultipleContainerOutput)
                            in prov_graph)
            members = list(prov_graph.objects(output_node, PROV.hadMember))
            self.assertEqual(len(members), 0)

    def test_provenance_annotation_container_multiple_output_multiple_annotations(self):
        activate(clear=True)
        container = process_multiple_container_output_multiple_annotations()
        deactivate()

        prov_data = save_provenance()

        # Read PROV information as RDF
        prov_graph = Graph()
        with io.StringIO(prov_data) as data_stream:
            prov_graph.parse(data_stream, format='turtle')

        # Check that the annotations exist
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessMultipleContainerOutputMultipleAnnotations)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessedMultipleContainerOutputLevel2)))
            ), 6)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessedMultipleContainerOutputLevel1)))
            ), 2)

        # FunctionExecution is ProcessMultipleContainerOutputMultipleAnnotations
        execution_uri = list(
            prov_graph.subjects(RDF.type, ALPACA.FunctionExecution))[0]
        self.assertTrue((execution_uri, RDF.type,
                         self.ONTOLOGY.ProcessMultipleContainerOutputMultipleAnnotations) in prov_graph)

        # Check returned values
        output_nodes = prov_graph.subjects(RDF.type,
                                self.ONTOLOGY.ProcessedMultipleContainerOutputLevel1)
        for output_node in output_nodes:
            self.assertTrue((None, PROV.hadMember, output_node) in prov_graph)
            self.assertTrue((output_node,
                             RDF.type, ALPACA.DataObjectEntity) in prov_graph)
            self.assertTrue((output_node,
                             RDF.type, self.ONTOLOGY.ProcessedMultipleContainerOutputLevel1)
                            in prov_graph)
            members = list(prov_graph.objects(output_node, PROV.hadMember))
            self.assertEqual(len(members), 3)
            for element in prov_graph.objects(output_node, PROV.hadMember):
                self.assertTrue(
                    (element, RDF.type, ALPACA.DataObjectEntity) in prov_graph)
                self.assertTrue(
                    (element, RDF.type, self.ONTOLOGY.ProcessedMultipleContainerOutputLevel2) in prov_graph)
                members = list(prov_graph.objects(element, PROV.hadMember))
                self.assertEqual(len(members), 0)

    def test_provenance_annotation_container_multiple_output_multiple_annotations_root(self):
        activate(clear=True)
        container = process_multiple_container_output_multiple_annotations_root()
        deactivate()

        prov_data = save_provenance()

        # Read PROV information as RDF
        prov_graph = Graph()
        with io.StringIO(prov_data) as data_stream:
            prov_graph.parse(data_stream, format='turtle')

        # Check that the annotations exist
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessMultipleContainerOutputMultipleAnnotationsRoot)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessedMultipleContainerOutputLevel2)))
            ), 6)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessedMultipleContainerOutputLevel1)))
            ), 2)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessedMultipleContainerOutputLevel0)))
            ), 1)

        # FunctionExecution is ProcessMultipleContainerOutputMultipleAnnotationsRoot
        execution_uri = list(
            prov_graph.subjects(RDF.type, ALPACA.FunctionExecution))[0]
        self.assertTrue((execution_uri, RDF.type,
                         self.ONTOLOGY.ProcessMultipleContainerOutputMultipleAnnotationsRoot) in prov_graph)

        # Check returned values
        output_nodes = prov_graph.subjects(RDF.type,
                                self.ONTOLOGY.ProcessedMultipleContainerOutputLevel0)
        for output_level0 in output_nodes:
            self.assertTrue((output_level0, PROV.wasGeneratedBy, execution_uri) in prov_graph)
            self.assertTrue((output_level0,
                             RDF.type, ALPACA.DataObjectEntity) in prov_graph)
            self.assertTrue((output_level0,
                             RDF.type, self.ONTOLOGY.ProcessedMultipleContainerOutputLevel0)
                            in prov_graph)
            members = list(prov_graph.objects(output_level0, PROV.hadMember))
            self.assertEqual(len(members), 2)
            for output_level1 in prov_graph.objects(output_level0, PROV.hadMember):
                self.assertTrue(
                    (output_level1, RDF.type, ALPACA.DataObjectEntity) in prov_graph)
                self.assertTrue(
                    (output_level1, RDF.type, self.ONTOLOGY.ProcessedMultipleContainerOutputLevel1) in prov_graph)
                members = list(prov_graph.objects(output_level1, PROV.hadMember))
                self.assertEqual(len(members), 3)
                for output_level2 in prov_graph.objects(output_level1, PROV.hadMember):
                    self.assertTrue(
                        (output_level2, RDF.type, ALPACA.DataObjectEntity) in prov_graph)
                    self.assertTrue(
                        (output_level2, RDF.type, self.ONTOLOGY.ProcessedMultipleContainerOutputLevel2) in prov_graph)
                    members = list(prov_graph.objects(output_level2, PROV.hadMember))
                    self.assertEqual(len(members), 0)

    def test_provenance_annotation_container_multiple_output_multiple_annotations_range(self):
        activate(clear=True)
        container = process_multiple_container_output_multiple_annotations_range()
        deactivate()

        prov_data = save_provenance()

        # Read PROV information as RDF
        prov_graph = Graph()
        with io.StringIO(prov_data) as data_stream:
            prov_graph.parse(data_stream, format='turtle')

        # Check that the annotations exist
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessMultipleContainerOutputMultipleAnnotationsRange)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessedMultipleContainerOutputLevel2)))
            ), 6)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessedMultipleContainerOutputLevel1)))
            ), 2)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessedMultipleContainerOutputLevel0)))
            ), 0)

        # FunctionExecution is ProcessMultipleContainerOutputMultipleAnnotationsRange
        execution_uri = list(
            prov_graph.subjects(RDF.type, ALPACA.FunctionExecution))[0]
        self.assertTrue((execution_uri, RDF.type,
                         self.ONTOLOGY.ProcessMultipleContainerOutputMultipleAnnotationsRange) in prov_graph)

        # Check returned values
        # First level was skipped, so only classes for Levels 1 and 2 should
        # be present
        output_nodes = prov_graph.subjects(RDF.type,
                                self.ONTOLOGY.ProcessedMultipleContainerOutputLevel1)
        for output_level1 in output_nodes:
            self.assertTrue((output_level1, PROV.wasGeneratedBy, execution_uri) in prov_graph)
            self.assertTrue((output_level1,
                             RDF.type, ALPACA.DataObjectEntity) in prov_graph)
            self.assertTrue((output_level1,
                             RDF.type, self.ONTOLOGY.ProcessedMultipleContainerOutputLevel1)
                            in prov_graph)
            members = list(prov_graph.objects(output_level1, PROV.hadMember))
            self.assertEqual(len(members), 3)
            for output_level2 in prov_graph.objects(output_level1, PROV.hadMember):
                self.assertTrue(
                    (output_level2, RDF.type, ALPACA.DataObjectEntity) in prov_graph)
                self.assertTrue(
                    (output_level2, RDF.type, self.ONTOLOGY.ProcessedMultipleContainerOutputLevel2) in prov_graph)
                members = list(prov_graph.objects(output_level2, PROV.hadMember))
                self.assertEqual(len(members), 0)

    def test_provenance_annotation_input(self):
        activate(clear=True)
        result = process_input_annotation(5, 6)
        deactivate()

        prov_data = save_provenance()

        # Read PROV information as RDF
        prov_graph = Graph()
        with io.StringIO(prov_data) as data_stream:
            prov_graph.parse(data_stream, format='turtle')

        # Check that the annotations exist
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessInputAnnotation)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.Input)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.Param)))
            ), 1)

        # FunctionExecution is ProcessInputAnnotation
        execution_uri = list(
            prov_graph.subjects(RDF.type, ALPACA.FunctionExecution))[0]
        self.assertTrue((execution_uri, RDF.type,
                         self.ONTOLOGY.ProcessInputAnnotation) in prov_graph)


        # Check input values
        input_nodes = prov_graph.objects(execution_uri, PROV.used)
        for input_node in input_nodes:
            self.assertTrue((execution_uri, PROV.used, input_node) in prov_graph)
            self.assertTrue((input_node,
                             RDF.type, ALPACA.DataObjectEntity) in prov_graph)
            self.assertTrue((input_node,
                             RDF.type, self.ONTOLOGY.Input) in prov_graph)

    def test_provenance_annotation_container_input(self):
        activate(clear=True)
        input_list = [20, 30, 40]
        result = process_container_input_annotation(5, input_list, 6)
        deactivate()

        prov_data = save_provenance()

        # Read PROV information as RDF
        prov_graph = Graph()
        with io.StringIO(prov_data) as data_stream:
            prov_graph.parse(data_stream, format='turtle')

        # Check that the annotations exist
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ProcessContainerInputAnnotation)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.Input)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.ContainerElementInput)))
            ), 3)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, self.ONTOLOGY.Param)))
            ), 1)

        # FunctionExecution is ProcessContainerInputAnnotation
        execution_uri = list(
            prov_graph.subjects(RDF.type, ALPACA.FunctionExecution))[0]
        self.assertTrue((execution_uri, RDF.type,
                         self.ONTOLOGY.ProcessContainerInputAnnotation) in prov_graph)


        # Check input values have the expected number of classes
        input_nodes = prov_graph.objects(execution_uri, PROV.used)
        input_node_count = Counter()
        for input_node in input_nodes:
            self.assertTrue((execution_uri, PROV.used, input_node) in prov_graph)
            for input_node_type in prov_graph.objects(input_node, RDF.type):
                input_node_count[input_node_type] += 1

        self.assertEqual(input_node_count[ALPACA.DataObjectEntity], 4)
        self.assertEqual(input_node_count[self.ONTOLOGY.Input], 1)
        self.assertEqual(input_node_count[self.ONTOLOGY.ContainerElementInput], 3)