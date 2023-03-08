import unittest

from pathlib import Path
import tempfile
import networkx as nx
from functools import partial
from collections import Counter

from alpaca import ProvenanceGraph, alpaca_setting


class ProvenanceGraphTestCase(unittest.TestCase):

    @staticmethod
    def _attr_comparison(attr_G1, attr_G2):
        return attr_G1 == attr_G2

    @staticmethod
    def _gexf_edge_comparison(attr_G1, attr_G2):
        # GEXF files add an `id` attribute to the edge, ignore it
        if 'id' in attr_G1:
            attr_G1.pop('id')
        if 'id' in attr_G2:
            attr_G2.pop('id')
        return attr_G1 == attr_G2

    @classmethod
    def setUpClass(cls):
        cls.ttl_path = Path(__file__).parent / "res"
        cls.temp_dir = tempfile.TemporaryDirectory(dir=cls.ttl_path,
                                                   suffix="tmp")
        cls.graph_comparison = partial(nx.is_isomorphic,
                                       node_match=cls._attr_comparison)
        alpaca_setting('authority', "my-authority")

    def test_graph_behavior_and_serialization(self):
        input_file = self.ttl_path / "input_output.ttl"
        graph = ProvenanceGraph(input_file)
        self.assertIsInstance(graph.graph, nx.DiGraph)
        self.assertEqual(len(graph.graph.nodes), 3)
        self.assertEqual(len(graph.graph.edges), 2)

        output_path = Path(self.temp_dir.name)

        # Test GEXF serialization
        gexf_file = output_path / "test.gexf"
        graph.save_gexf(gexf_file)
        self.assertTrue(gexf_file.exists())
        read_gexf = nx.read_gexf(gexf_file)
        self.assertTrue(self.graph_comparison(
            read_gexf, graph.graph, edge_match=self._gexf_edge_comparison))

        # Test GraphML serialization
        graphml_file = output_path / "test.graphml"
        graph.save_graphml(graphml_file)
        self.assertTrue(graphml_file.exists())
        read_graphml = nx.read_graphml(graphml_file)
        self.assertTrue(self.graph_comparison(read_graphml, graph.graph,
                                              edge_match=self._attr_comparison))

    def test_use_name_in_parameter(self):
        node = "urn:fz-juelich.de:alpaca:function_execution:Python:111111:999999:test.test_function#12345"
        input_file = self.ttl_path / "input_output.ttl"
        graph_use_name = ProvenanceGraph(input_file)
        graph_dont_use_name = ProvenanceGraph(input_file,
                                              use_name_in_parameter=False)
        use_name_attrs = graph_use_name.graph.nodes[node]
        dont_use_name_attrs = graph_dont_use_name.graph.nodes[node]

        self.assertTrue('test_function:param_1' in use_name_attrs)
        self.assertTrue('parameter:param_1' in dont_use_name_attrs)
        self.assertFalse('parameter:param_1' in use_name_attrs)
        self.assertFalse('test_function:param_1' in dont_use_name_attrs)
        self.assertEqual(use_name_attrs['test_function:param_1'], '5')
        self.assertEqual(dont_use_name_attrs['parameter:param_1'], '5')

    def test_remove_none(self):
        node = "urn:fz-juelich.de:alpaca:object:Python:builtins.NoneType:777777"
        input_file = self.ttl_path / "file_output.ttl"
        graph_with_none = ProvenanceGraph(input_file, remove_none=False)
        graph_without_none = ProvenanceGraph(input_file, remove_none=True)

        self.assertTrue(node in graph_with_none.graph.nodes)
        self.assertFalse(node in graph_without_none.graph.nodes)
        self.assertEqual(len(graph_with_none.graph.nodes), 4)
        self.assertEqual(len(graph_without_none.graph.nodes), 3)

    def test_remove_none_no_output_function(self):
        node = "urn:fz-juelich.de:alpaca:object:Python:builtins.NoneType:777777"
        input_file = self.ttl_path / "none_output.ttl"
        graph_with_none = ProvenanceGraph(input_file, remove_none=False)
        graph_without_none = ProvenanceGraph(input_file, remove_none=True)

        self.assertTrue(node in graph_with_none.graph.nodes)
        self.assertFalse(node in graph_without_none.graph.nodes)
        self.assertEqual(len(graph_with_none.graph.nodes), 3)
        self.assertEqual(len(graph_without_none.graph.nodes), 2)


    def test_memberships(self):
        input_file = self.ttl_path / "multiple_memberships.ttl"
        graph = ProvenanceGraph(input_file)

        self.assertEqual(len(graph.graph.nodes), 7)
        for node in (
        "urn:fz-juelich.de:alpaca:object:Python:builtins.list:3333332",
        "urn:fz-juelich.de:alpaca:object:Python:builtins.list:23333332",
        "urn:fz-juelich.de:alpaca:object:Python:test.Container:333333",
        "urn:fz-juelich.de:alpaca:object:Python:test.InputObject:12345",
        "urn:fz-juelich.de:alpaca:object:Python:test.SuperContainer:2333333"):
            self.assertTrue(node in graph.graph.nodes)

        for expected_edge, expected_label in zip(
                ((
                 "urn:fz-juelich.de:alpaca:object:Python:test.SuperContainer:2333333",
                 "urn:fz-juelich.de:alpaca:object:Python:builtins.list:23333332"),
                 (
                 "urn:fz-juelich.de:alpaca:object:Python:builtins.list:23333332",
                 "urn:fz-juelich.de:alpaca:object:Python:test.Container:333333"),
                 (
                 "urn:fz-juelich.de:alpaca:object:Python:test.Container:333333",
                 "urn:fz-juelich.de:alpaca:object:Python:builtins.list:3333332"),
                 (
                 "urn:fz-juelich.de:alpaca:object:Python:builtins.list:3333332",
                 "urn:fz-juelich.de:alpaca:object:Python:test.InputObject:12345")),
                (".containers", "[0]", ".inputs", "[1]")):
            self.assertTrue(expected_edge in graph.graph.edges)
            self.assertTrue(graph.graph.edges[expected_edge]['membership'])
            self.assertEqual(graph.graph.edges[expected_edge]['label'],
                             expected_label)

    def test_membership_condensing(self):
        input_file = self.ttl_path / "multiple_memberships.ttl"
        graph = ProvenanceGraph(input_file)
        graph.condense_memberships()

        self.assertEqual(len(graph.graph.nodes), 4)

        for node in (
        "urn:fz-juelich.de:alpaca:object:Python:test.InputObject:12345",
        "urn:fz-juelich.de:alpaca:object:Python:test.SuperContainer:2333333"):
            self.assertTrue(node in graph.graph.nodes)

        for node in (
        "urn:fz-juelich.de:alpaca:object:Python:builtins.list:3333332",
        "urn:fz-juelich.de:alpaca:object:Python:builtins.list:23333332",
        "urn:fz-juelich.de:alpaca:object:Python:test.Container:333333"):
            self.assertFalse(node in graph.graph.nodes)

        for edge in ((
                     "urn:fz-juelich.de:alpaca:object:Python:test.SuperContainer:2333333",
                     "urn:fz-juelich.de:alpaca:object:Python:builtins.list:23333332"),
                     (
                     "urn:fz-juelich.de:alpaca:object:Python:builtins.list:23333332",
                     "urn:fz-juelich.de:alpaca:object:Python:test.Container:333333"),
                     (
                     "urn:fz-juelich.de:alpaca:object:Python:test.Container:333333",
                     "urn:fz-juelich.de:alpaca:object:Python:builtins.list:3333332"),
                     (
                     "urn:fz-juelich.de:alpaca:object:Python:builtins.list:3333332",
                     "urn:fz-juelich.de:alpaca:object:Python:test.InputObject:12345")):
            self.assertFalse(edge in graph.graph.edges)

        expected_edge = (
        "urn:fz-juelich.de:alpaca:object:Python:test.SuperContainer:2333333",
        "urn:fz-juelich.de:alpaca:object:Python:test.InputObject:12345")

        expected_label = ".containers[0].inputs[1]"

        self.assertTrue(expected_edge in graph.graph.edges)
        self.assertTrue(graph.graph.edges[expected_edge]['membership'])
        self.assertEqual(graph.graph.edges[expected_edge]['label'],
                         expected_label)

    def test_membership_condensing_with_preservation(self):
        input_file = self.ttl_path / "multiple_memberships.ttl"
        graph = ProvenanceGraph(input_file)
        graph.condense_memberships(preserve=['Container'])

        self.assertEqual(len(graph.graph.nodes), 5)

        for node in (
        "urn:fz-juelich.de:alpaca:object:Python:test.InputObject:12345",
        "urn:fz-juelich.de:alpaca:object:Python:test.SuperContainer:2333333",
        "urn:fz-juelich.de:alpaca:object:Python:test.Container:333333"):
            self.assertTrue(node in graph.graph.nodes)

        for node in (
        "urn:fz-juelich.de:alpaca:object:Python:builtins.list:3333332",
        "urn:fz-juelich.de:alpaca:object:Python:builtins.list:23333332"):
            self.assertFalse(node in graph.graph.nodes)

        for edge in ((
                     "urn:fz-juelich.de:alpaca:object:Python:test.SuperContainer:2333333",
                     "urn:fz-juelich.de:alpaca:object:Python:builtins.list:23333332"),
                     (
                     "urn:fz-juelich.de:alpaca:object:Python:builtins.list:23333332",
                     "urn:fz-juelich.de:alpaca:object:Python:test.Container:333333"),
                     (
                     "urn:fz-juelich.de:alpaca:object:Python:test.Container:333333",
                     "urn:fz-juelich.de:alpaca:object:Python:builtins.list:3333332"),
                     (
                     "urn:fz-juelich.de:alpaca:object:Python:builtins.list:3333332",
                     "urn:fz-juelich.de:alpaca:object:Python:test.InputObject:12345")):
            self.assertFalse(edge in graph.graph.edges)

        for expected_edge, expected_label in zip(
                ((
                 "urn:fz-juelich.de:alpaca:object:Python:test.SuperContainer:2333333",
                 "urn:fz-juelich.de:alpaca:object:Python:test.Container:333333"),
                 (
                 "urn:fz-juelich.de:alpaca:object:Python:test.Container:333333",
                 "urn:fz-juelich.de:alpaca:object:Python:test.InputObject:12345")),
                (".containers[0]", ".inputs[1]")):
            self.assertTrue(expected_edge in graph.graph.edges)
            self.assertTrue(graph.graph.edges[expected_edge]['membership'])
            self.assertEqual(graph.graph.edges[expected_edge]['label'],
                             expected_label)

    def test_strip_namespace(self):
        input_file = self.ttl_path / "metadata.ttl"

        graph = ProvenanceGraph(input_file, attributes=['name'],
                                annotations=['sua'], strip_namespace=True)
        node_attrs = graph.graph.nodes[
            "urn:fz-juelich.de:alpaca:object:Python:neo.core.SpikeTrain:54321"]

        self.assertEqual(node_attrs["name"], "Spiketrain#1")
        self.assertEqual(node_attrs["sua"], "false")

    def test_use_class_in_method_name(self):
        input_file = self.ttl_path / "class_method.ttl"

        graph = ProvenanceGraph(input_file, attributes=None,
                                annotations=None,
                                use_class_in_method_name=True)
        node_attrs = graph.graph.nodes[
            "urn:fz-juelich.de:alpaca:function_execution:Python:111111:999999:test.ObjectWithMethod.process#12345"]

        self.assertEqual(node_attrs["label"], "ObjectWithMethod.process")

    def test_no_use_class_in_method_name(self):
        input_file = self.ttl_path / "class_method.ttl"

        graph = ProvenanceGraph(input_file, attributes=None,
                                annotations=None,
                                use_class_in_method_name=False)
        node_attrs = graph.graph.nodes[
            "urn:fz-juelich.de:alpaca:function_execution:Python:111111:999999:test.ObjectWithMethod.process#12345"]

        self.assertEqual(node_attrs["label"], "process")

    def test_no_strip_namespace(self):
        input_file = self.ttl_path / "metadata.ttl"

        graph = ProvenanceGraph(input_file, attributes=['name'],
                                annotations=['sua'], strip_namespace=False)
        node_attrs = graph.graph.nodes[
            "urn:fz-juelich.de:alpaca:object:Python:neo.core.SpikeTrain:54321"]

        self.assertEqual(node_attrs["attribute:name"], "Spiketrain#1")
        self.assertEqual(node_attrs["annotation:sua"], "false")

    def test_attributes(self):
        input_file = self.ttl_path / "metadata.ttl"
        graph = ProvenanceGraph(input_file, attributes=['metadata_2'])

        node_attrs = graph.graph.nodes[
            "urn:fz-juelich.de:alpaca:object:Python:test.InputObject:12345"]

        self.assertEqual(node_attrs["metadata_2"], "5")

        for annotation in ("metadata_1", "metadata_3", "metadata_4"):
            self.assertTrue(annotation not in node_attrs)

        node_attrs = graph.graph.nodes[
            "urn:fz-juelich.de:alpaca:object:Python:neo.core.SpikeTrain:54321"]

        self.assertTrue("name" not in node_attrs)

    def test_annotations(self):
        input_file = self.ttl_path / "metadata.ttl"
        graph = ProvenanceGraph(input_file, annotations=['sua'])

        node_attrs = graph.graph.nodes[
            "urn:fz-juelich.de:alpaca:object:Python:neo.core.SpikeTrain:54321"]

        self.assertEqual(node_attrs['sua'], "false")

        for annotation in ("channel", "complexity", "event"):
            self.assertTrue(annotation not in node_attrs)

    def test_all_annotations(self):
        input_file = self.ttl_path / "metadata.ttl"
        graph = ProvenanceGraph(input_file, annotations='all')

        annotations_node = "urn:fz-juelich.de:alpaca:object:Python:neo.core.SpikeTrain:54321"

        expected_annotations = {"sua": "false",
                                "channel": "56",
                                "complexity": "[0 1 2 3]",
                                "event": "[ True False False]"}

        attributes_node = "urn:fz-juelich.de:alpaca:object:Python:test.InputObject:12345"

        expected_attributes = {"metadata_1": "value1",
                               "metadata_2": "5",
                               "metadata_3": "5.0",
                               "metadata_4": "true"}

        node_attrs = graph.graph.nodes[annotations_node]
        for key, value in expected_annotations.items():
            self.assertTrue(key in node_attrs)
            self.assertEqual(node_attrs[key], value)

        node_attrs = graph.graph.nodes[attributes_node]
        for key, value in expected_attributes.items():
            self.assertTrue(key not in node_attrs)

    def test_all_attributes(self):
        input_file = self.ttl_path / "metadata.ttl"
        graph = ProvenanceGraph(input_file, attributes='all')

        annotations_node = "urn:fz-juelich.de:alpaca:object:Python:neo.core.SpikeTrain:54321"

        expected_annotations = {"sua": "false",
                                "channel": "56",
                                "complexity": "[0 1 2 3]",
                                "event": "[ True False False]"}

        attributes_node = "urn:fz-juelich.de:alpaca:object:Python:test.InputObject:12345"

        expected_attributes = {"metadata_1": "value1",
                               "metadata_2": "5",
                               "metadata_3": "5.0",
                               "metadata_4": "true"}

        node_attrs = graph.graph.nodes[annotations_node]
        for key, value in expected_annotations.items():
            self.assertTrue(key not in node_attrs)

        self.assertEqual(node_attrs['name'], "Spiketrain#1")

        node_attrs = graph.graph.nodes[attributes_node]
        for key, value in expected_attributes.items():
            self.assertTrue(key in node_attrs)
            self.assertEqual(node_attrs[key], value)


class GraphAggregationTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ttl_path = Path(__file__).parent / "res"
        input_file = cls.ttl_path / "parallel_graph.ttl"
        cls.graph = ProvenanceGraph(input_file, attributes=['shape', 'metadata'])
        alpaca_setting('authority', "my-authority")

    def test_serialization(self):
        temp_dir = tempfile.TemporaryDirectory(dir=self.ttl_path, suffix="tmp")
        output_path = Path(temp_dir.name)

        gexf_file = output_path / "test.gexf"
        self.graph.aggregate({}, output_file=gexf_file)
        self.assertTrue(gexf_file.exists())

        graphml_file = output_path / "test.graphml"
        self.graph.aggregate({}, output_file=graphml_file)
        self.assertTrue(graphml_file.exists())

        with self.assertRaises(ValueError):
            self.graph.aggregate({}, output_file=output_path / "test.invalid")

    def test_overall_aggregation(self):
        aggregated = self.graph.aggregate({}, use_function_parameters=False,
                                          output_file=None)
        nodes = aggregated.nodes

        self.assertEqual(len(nodes), 4)

        expected_values_per_node = {
            'OutputObject': {'metadata': "0;1",
                             'shape': "(2,);(3,);(4,);(5,)"},
            'InputObject': {'metadata': "5",
                            'shape': "(2,);(3,);(4,);(5,)"},
            'process': {'process:value': "0;1;2;3"},
            'list': {}
        }

        all_labels = [nodes[node]['label'] for node in nodes]
        counts = Counter(all_labels)
        self.assertEqual(counts['OutputObject'], 1)
        self.assertEqual(counts['InputObject'], 1)
        self.assertEqual(counts['process'], 1)
        self.assertEqual(counts['list'], 1)

        for node, attrs in nodes.items():
            label = attrs['label']
            with self.subTest(f"Node label {label}"):
                self.assertTrue(label in expected_values_per_node)
                for key, value in expected_values_per_node[label].items():
                    self.assertEqual(attrs[key], value)

    def test_aggregation_by_attribute(self):
        aggregated = self.graph.aggregate({'InputObject': ('shape',)},
                                          use_function_parameters=False,
                                          output_file=None)
        nodes = aggregated.nodes

        self.assertEqual(len(nodes), 7)

        expected_values_per_node = {
            'OutputObject': {'metadata': "0;1",
                             'shape': "(2,);(3,);(4,);(5,)"},
            'InputObject': {'metadata': "5",
                            'shape': ["(2,)", "(3,)", "(4,)", "(5,)"]},
            'process': {'process:value': "0;1;2;3"},
            'list': {}
        }

        all_labels = [nodes[node]['label'] for node in nodes]
        counts = Counter(all_labels)
        self.assertEqual(counts['OutputObject'], 1)
        self.assertEqual(counts['InputObject'], 4)
        self.assertEqual(counts['process'], 1)
        self.assertEqual(counts['list'], 1)

        for node, attrs in nodes.items():
            label = attrs['label']
            with self.subTest(f"Node label {label}"):
                self.assertTrue(label in expected_values_per_node)
                for key, value in expected_values_per_node[label].items():
                    if not isinstance(value, list):
                        self.assertEqual(attrs[key], value)
                    else:
                        self.assertTrue(attrs[key] in value)

    def test_aggregation_by_attribute_with_function(self):
        aggregated = self.graph.aggregate({'InputObject': ('shape',)},
                                          use_function_parameters=True,
                                          output_file=None)
        nodes = aggregated.nodes

        self.assertEqual(len(nodes), 10)

        expected_values_per_node = {
            'OutputObject': {'metadata': "0;1",
                             'shape': "(2,);(3,);(4,);(5,)"},
            'InputObject': {'metadata': "5",
                            'shape': ["(2,)", "(3,)", "(4,)", "(5,)"]},
            'process': {'process:value': ["0", "1", "2", "3"]},
            'list': {}
        }

        all_labels = [nodes[node]['label'] for node in nodes]
        counts = Counter(all_labels)
        self.assertEqual(counts['OutputObject'], 1)
        self.assertEqual(counts['InputObject'], 4)
        self.assertEqual(counts['process'], 4)
        self.assertEqual(counts['list'], 1)

        for node, attrs in nodes.items():
            label = attrs['label']
            with self.subTest(f"Node label {label}"):
                self.assertTrue(label in expected_values_per_node)
                for key, value in expected_values_per_node[label].items():
                    if not isinstance(value, list):
                        self.assertEqual(attrs[key], value)
                    else:
                        self.assertTrue(attrs[key] in value)


if __name__ == "__main__":
    unittest.main()
