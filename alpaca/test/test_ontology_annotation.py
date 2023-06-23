import unittest
import io
from rdflib import Literal, URIRef, Namespace, Graph, RDF, PROV

from alpaca import (activate, deactivate, Provenance, save_provenance,
                    annotate_function, annotate_object)
from alpaca.ontology.annotation import (OntologyInformation,
                                        update_ontology_information)
from alpaca.ontology import ALPACA


# Ontology namespace definition used for the tests
EXAMPLE_NS = {'ontology': "http://example.org/ontology#"}


##############################
# Test objects to be annotated
##############################

class InputObject:
    pass

@annotate_object("ontology:OutputObject", namespaces=EXAMPLE_NS,
                 attributes={'name': "ontology:Attribute"})
class OutputObject:
    def __init__(self, name, channel):
        self.name = name
        self.channel = channel

# Ontology annotation of objects using function

update_ontology_information(InputObject, "data_object",
                            "ontology:InputObject",
                            namespaces=EXAMPLE_NS)


#######################################################
# Test functions to be annotated and provenance tracked
#######################################################

@Provenance(inputs=['input'])
@annotate_function("ontology:ProcessFunction", namespaces=EXAMPLE_NS,
                   arguments={'param_1': "ontology:Parameter"},
                   returns={0: "ontology:ProcessedData"})
def process(input, param_1):
    return OutputObject("SpikeTrain#1", 45)


@Provenance(inputs=['input'])
@annotate_function("ontology:ProcessFunctionMultiple", namespaces=EXAMPLE_NS,
                   arguments={'param_1': "ontology:Parameter"},
                   returns={1: "ontology:ProcessedDataMultiple"})
def process_multiple(input, param_1):
    return "not_annotated", OutputObject("SpikeTrain#2", 34)


############
# Unit tests
############

class OntologyAnnotationTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create rdflib Namespace for tests
        cls.ONTOLOGY = Namespace(EXAMPLE_NS['ontology'])

    def test_annotation_object_input(self):
        obj = InputObject()
        self.assertTrue(OntologyInformation.has_ontology(obj))
        info = OntologyInformation(obj)
        self.assertEqual(info.get_iri("data_object"),
                         URIRef("http://example.org/ontology#InputObject"))

    def test_annotation_object_output(self):
        obj = OutputObject("test", 45)
        self.assertTrue(OntologyInformation.has_ontology(obj))
        info = OntologyInformation(obj)
        self.assertEqual(info.get_iri("data_object"),
                         URIRef("http://example.org/ontology#OutputObject"))
        self.assertEqual(info.get_iri("attributes", "name"),
                         URIRef("http://example.org/ontology#Attribute"))

    def test_annotation_function(self):
        self.assertTrue(OntologyInformation.has_ontology(process))
        info = OntologyInformation(process)
        self.assertEqual(info.get_iri("function"),
                         URIRef("http://example.org/ontology#ProcessFunction"))
        self.assertEqual(info.get_iri("arguments", "param_1"),
                         URIRef("http://example.org/ontology#Parameter"))
        self.assertEqual(info.get_iri("returns", 0),
                         URIRef("http://example.org/ontology#ProcessedData"))

    def test_annotation_function_multiple(self):
        self.assertTrue(OntologyInformation.has_ontology(process_multiple))
        info = OntologyInformation(process_multiple)
        self.assertEqual(info.get_iri("function"),
                         URIRef("http://example.org/ontology#ProcessFunctionMultiple"))
        self.assertEqual(info.get_iri("arguments", "param_1"),
                         URIRef("http://example.org/ontology#Parameter"))
        self.assertEqual(info.get_iri("returns", 1),
                         URIRef("http://example.org/ontology#ProcessedDataMultiple"))


    def test_invalid_object_annotations(self):
        obj = InputObject()
        info = OntologyInformation(obj)
        self.assertIsNone(info.get_iri("attributes", "name"))

        output_obj = OutputObject("test", 45)
        output_info = OntologyInformation(output_obj)
        self.assertIsNone(info.get_iri("attributes", "channel"))
        self.assertIsNone(info.get_iri("non_existent"))
        self.assertIsNone(info.get_iri("non_existent", "test"))

    def test_invalid_function_annotation_parameters(self):
        with self.assertRaises(ValueError):
            annotate_function("iri", namespaces=EXAMPLE_NS,
                              attributes={"test": "ontology:Attribute"})(process)

    def test_namespaces(self):
        input_obj = InputObject()
        output_obj = OutputObject("test", 45)

        input_info = OntologyInformation(input_obj)
        output_info = OntologyInformation(output_obj)
        function_info = OntologyInformation(process)

        for info in (input_info, output_info, function_info):
            self.assertEqual(info.namespaces['ontology'],
                             self.ONTOLOGY)
            self.assertTupleEqual(tuple(info.namespaces.keys()), ('ontology',))

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
        execution_iri = list(
            prov_graph.subjects(RDF.type, ALPACA.FunctionExecution))[0]
        self.assertTrue((execution_iri,
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
                         PROV.wasGeneratedBy, execution_iri) in prov_graph)
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
            name = prov_graph.value(attribute, ALPACA.pairName)
            value = prov_graph.value(attribute, ALPACA.pairValue)
            self.assertEqual(value.toPython(),
                             expected_attributes[name.toPython()])

        # Check input value
        input_node = list(
            prov_graph.subjects(RDF.type, self.ONTOLOGY.InputObject))[0]
        self.assertTrue((execution_iri, PROV.used, input_node) in prov_graph)
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

        # FunctionExecution is ProcessFunction
        execution_iri = list(
            prov_graph.subjects(RDF.type, ALPACA.FunctionExecution))[0]
        self.assertTrue((execution_iri, RDF.type,
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
                         PROV.wasGeneratedBy, execution_iri) in prov_graph)
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
            name = prov_graph.value(attribute, ALPACA.pairName)
            value = prov_graph.value(attribute, ALPACA.pairValue)
            self.assertEqual(value.toPython(),
                             expected_attributes[name.toPython()])

        # Check input value
        input_node = list(
            prov_graph.subjects(RDF.type, self.ONTOLOGY.InputObject))[0]
        self.assertTrue((execution_iri,
                         PROV.used, input_node) in prov_graph)
        self.assertTrue((input_node,
                         RDF.type, ALPACA.DataObjectEntity) in prov_graph)
        self.assertTrue((output_node,
                         PROV.wasDerivedFrom, input_node) in prov_graph)
