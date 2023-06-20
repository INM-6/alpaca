import unittest
import io
from rdflib import Literal, URIRef, Namespace, Graph, RDF, PROV

from alpaca import (activate, deactivate, Provenance,
                    annotate_function_with_ontology, save_provenance)
from alpaca.ontology.annotation import (OntologyInformation,
                                        update_ontology_information)
from alpaca.ontology import ALPACA


# Ontology namespace used for the tests
EXAMPLE_NS = {'ontology': "http://example.org/ontology#"}


class InputObject:
    pass


class OutputObject:
    def __init__(self, name, channel):
        self.name = name
        self.annotations= {'channel': channel}


@Provenance(inputs=['input'])
@annotate_function_with_ontology("ontology:ProcessFunction",
                                arguments={'param_1': "ontology:Parameter"},
                                returns={0: "ontology:ProcessedData"},
                                namespaces=EXAMPLE_NS)
def process(input, param_1):
    return OutputObject("SpikeTrain#1", 45)


update_ontology_information(OutputObject, "data_object",
                            "ontology:OutputObject",
                            attributes={'name': "ontology:Attribute"},
                            annotations={'channel': "ontology:Annotation"},
                            namespaces=EXAMPLE_NS)


update_ontology_information(InputObject, "data_object",
                            "ontology:InputObject",
                            namespaces=EXAMPLE_NS)


class OntologyAnnotationTestCase(unittest.TestCase):

    def test_annotation_input(self):
        obj = InputObject()
        self.assertTrue(OntologyInformation.has_ontology(obj))
        info = OntologyInformation(obj)
        self.assertEqual(info.get_iri("data_object"),
                         URIRef("http://example.org/ontology#InputObject"))

    def test_annotation_output(self):
        obj = OutputObject("test", 45)
        self.assertTrue(OntologyInformation.has_ontology(obj))
        info = OntologyInformation(obj)
        self.assertEqual(info.get_iri("data_object"),
                         URIRef("http://example.org/ontology#OutputObject"))
        self.assertEqual(info.get_iri("annotations", "channel"),
                         URIRef("http://example.org/ontology#Annotation"))
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

    def test_invalid_annotation(self):
        obj = InputObject()
        info = OntologyInformation(obj)
        self.assertIsNone(info.get_iri("attributes", "name"))

        output_obj = OutputObject("test", 45)
        output_info = OntologyInformation(output_obj)
        self.assertIsNone(info.get_iri("attributes", "shape"))
        self.assertIsNone(info.get_iri("non_existent"))
        self.assertIsNone(info.get_iri("non_existent", "test"))

    def test_invalid_function_annotation(self):
        with self.assertRaises(ValueError):
            annotate_function_with_ontology("iri",
                attributes={"test": "ontology:Attribute"},
                namespaces=EXAMPLE_NS)(process)

    def test_namespaces(self):
        input_obj = InputObject()
        output_obj = OutputObject("test", 45)

        input_info = OntologyInformation(input_obj)
        output_info = OntologyInformation(output_obj)
        function_info = OntologyInformation(process)

        for info in (input_info, output_info, function_info):
            self.assertEqual(info.namespaces['ontology'],
                             Namespace(EXAMPLE_NS['ontology']))
            self.assertTupleEqual(tuple(info.namespaces.keys()), ('ontology',))

    def test_provenance_annotation(self):
        activate()
        input_object = InputObject()
        output_object = process(input_object, 34)
        deactivate()

        prov_data = save_provenance()

        # Read PROV information as RDF
        prov_graph = Graph()
        with io.StringIO(prov_data) as data_stream:
            prov_graph.parse(data_stream, format='turtle')

        # Create namespace for tests
        ONTOLOGY = Namespace(EXAMPLE_NS['ontology'])

        # Check that the annotations exist (1 per class is expected)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, ONTOLOGY.Parameter)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, ONTOLOGY.ProcessFunction)))
            ), 1)
        self.assertEqual(
            len(list(prov_graph.triples(
                (None, RDF.type, ONTOLOGY.ProcessedData)))
            ), 1)


        # FunctionExecution is ProcessFunction
        execution_iri = list(
            prov_graph.subjects(RDF.type, ALPACA.FunctionExecution))[0]
        self.assertTrue((execution_iri, RDF.type, ONTOLOGY.ProcessFunction) in prov_graph)

        # Check parameter name
        parameter_node = list(
            prov_graph.subjects(RDF.type, ONTOLOGY.Parameter))[0]
        self.assertTrue((parameter_node, ALPACA.pairName, Literal("param_1")) in prov_graph)
        self.assertTrue((parameter_node, ALPACA.pairValue, Literal(34)) in prov_graph)

        # Check returned value
        output_node = list(
            prov_graph.subjects(RDF.type, ONTOLOGY.ProcessedData))[0]
        self.assertTrue((output_node, PROV.wasGeneratedBy, execution_iri) in prov_graph)
        self.assertTrue((output_node, RDF.type, ALPACA.DataObjectEntity) in prov_graph)

        # execution_iri = list(
        #     prov_graph.predicate_objects(
        #         RDF.type, ALPACA.FunctionExecution))
        # print(prov_graph.triples((execution_iri, RDF.type, ONTOLOGY.ProcessFunction)))

