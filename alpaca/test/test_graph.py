import sys
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

    def test_remove_multiple_attributes(self):
        input_file = self.ttl_path / "metadata.ttl"
        graph = ProvenanceGraph(input_file, attributes='all',
                                annotations='all')

        graph.remove_attributes('metadata_4', 'sua', 'Time Interval')

        annotations_node = "urn:fz-juelich.de:alpaca:object:Python:neo.core.SpikeTrain:54321"

        expected_annotations = {"channel": "56",
                                "complexity": "[0 1 2 3]",
                                "event": "[ True False False]"}

        attributes_node = "urn:fz-juelich.de:alpaca:object:Python:test.InputObject:12345"

        expected_attributes = {"metadata_1": "value1",
                               "metadata_2": "5",
                               "metadata_3": "5.0"}

        node_attrs = graph.graph.nodes[annotations_node]
        for key, value in expected_annotations.items():
            self.assertTrue(key in node_attrs)
            self.assertEqual(node_attrs[key], value)

        self.assertEqual(node_attrs['name'], "Spiketrain#1")

        node_attrs = graph.graph.nodes[attributes_node]
        for key, value in expected_attributes.items():
            self.assertTrue(key in node_attrs)
            self.assertEqual(node_attrs[key], value)

        for _, node_attrs in graph.graph.nodes(data=True):
            self.assertTrue("Time Interval" not in node_attrs)
            self.assertTrue("sua" not in node_attrs)
            self.assertTrue("metadata_4" not in node_attrs)

    def test_remove_attributes(self):
        input_file = self.ttl_path / "metadata.ttl"
        graph = ProvenanceGraph(input_file, attributes='all',
                                annotations='all')

        graph.remove_attributes('metadata_4')

        annotations_node = "urn:fz-juelich.de:alpaca:object:Python:neo.core.SpikeTrain:54321"

        expected_annotations = {"sua": "false",
                                "channel": "56",
                                "complexity": "[0 1 2 3]",
                                "event": "[ True False False]"}

        attributes_node = "urn:fz-juelich.de:alpaca:object:Python:test.InputObject:12345"

        expected_attributes = {"metadata_1": "value1",
                               "metadata_2": "5",
                               "metadata_3": "5.0"}

        node_attrs = graph.graph.nodes[annotations_node]
        for key, value in expected_annotations.items():
            self.assertTrue(key in node_attrs)
            self.assertEqual(node_attrs[key], value)

        self.assertEqual(node_attrs['name'], "Spiketrain#1")

        node_attrs = graph.graph.nodes[attributes_node]
        for key, value in expected_attributes.items():
            self.assertTrue(key in node_attrs)
            self.assertEqual(node_attrs[key], value)

        for _, node_attrs in graph.graph.nodes(data=True):
            self.assertTrue("Time Interval" in node_attrs)
            self.assertTrue("metadata_4" not in node_attrs)

    def test_remove_attributes_aggregation(self):
        input_file = self.ttl_path / "metadata.ttl"
        graph = ProvenanceGraph(input_file, attributes='all',
                                annotations='all')
        aggregated = graph.aggregate({},
                                     remove_attributes="Time Interval")

        for _, node_attrs in aggregated.nodes(data=True):
            self.assertTrue("Time Interval" not in node_attrs)

    def test_remove_multiple_attributes_aggregation(self):
        input_file = self.ttl_path / "metadata.ttl"
        graph = ProvenanceGraph(input_file, attributes='all',
                                annotations='all')
        aggregated = graph.aggregate({},
                                     remove_attributes=("Time Interval",
                                                        "sua"))

        for _, node_attrs in aggregated.nodes(data=True):
            self.assertTrue("Time Interval" not in node_attrs)
            self.assertTrue("sua" not in node_attrs)

    def test_value_attribute(self):
        input_file = self.ttl_path / "values.ttl"
        graph = ProvenanceGraph(input_file, attributes='all',
                                annotations='all', value_attribute='value')

        node_values_by_id = {
            "urn:fz-juelich.de:alpaca:object:Python:builtins.int:543211": 1,
            "urn:fz-juelich.de:alpaca:object:Python:builtins.float:543212": 1.1,
            "urn:fz-juelich.de:alpaca:object:Python:builtins.str:543213": "test",
            "urn:fz-juelich.de:alpaca:object:Python:builtins.complex:543214": "(3+5j)",
            "urn:fz-juelich.de:alpaca:object:Python:builtins.bool:543215": True,
            "urn:fz-juelich.de:alpaca:object:Python:numpy.float32:543216": 1.2,
            "urn:fz-juelich.de:alpaca:object:Python:numpy.float64:543217": 1.3,
            "urn:fz-juelich.de:alpaca:object:Python:numpy.int64:543218": 2,
            "urn:fz-juelich.de:alpaca:object:Python:numpy.int32:543219": 3,
            "urn:fz-juelich.de:alpaca:object:Python:numpy.int16:5432110": -4,
            "urn:fz-juelich.de:alpaca:object:Python:builtins.dict:5432111": "{'id': [1, 2, 3], 'value': {4, 5, 6}}",
            "urn:fz-juelich.de:alpaca:object:Python:test.InputObject:12345": None,
            "urn:fz-juelich.de:alpaca:object:Python:test.OutputObject:54321": None,
        }

        for node, node_attrs in graph.graph.nodes(data=True):
            if node_attrs['type'] == 'object':
                expected_value = node_values_by_id[node]
                self.assertEqual(expected_value, node_attrs.get('value', None))


class GraphTimeIntervalTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        ttl_path = Path(__file__).parent / "res"
        cls.input_file = ttl_path / "parallel_graph.ttl"
        alpaca_setting('authority', "my-authority")

    def test_use_time_interval(self):
        graph = ProvenanceGraph(self.input_file, time_intervals=True)
        for _, attrs in graph.graph.nodes(data=True):
            self.assertFalse("gephi_interval" in attrs)
            self.assertTrue("Time Interval" in attrs)

    def test_not_use_time_interval(self):
        graph = ProvenanceGraph(self.input_file, time_intervals=False)
        for _, attrs in graph.graph.nodes(data=True):
            self.assertFalse("gephi_interval" in attrs)
            self.assertFalse("Time Interval" in attrs)

    def test_intervals(self):
        expected_intervals = {
"urn:fz-juelich.de:alpaca:object:Python:__main__.OutputObject:3934c99ea6197963f4bc7413932f6ce6dd800b08": "<[3.0,3.0]>",
            "urn:fz-juelich.de:alpaca:object:Python:__main__.OutputObject:4ef19b49bcf029faae5349020a54096d53398c95": "<[1.0,1.0]>",
            "urn:fz-juelich.de:alpaca:object:Python:__main__.OutputObject:93f4a32cb869a3e115e3382fd0fd49ab4ea0c8df": "<[2.0,2.0]>",
            "urn:fz-juelich.de:alpaca:object:Python:__main__.OutputObject:97ce94acf4ec4e2cb7d1319b798dbdd187df9558": "<[4.0,4.0]>",
            "urn:fz-juelich.de:alpaca:object:Python:builtins.list:f801594e5cebdc73ba8815e8ad66cab5cd86d2bf": "<[1.0,1.0];[2.0,2.0];[3.0,3.0];[4.0,4.0]>",
            "urn:fz-juelich.de:alpaca:function_execution:Python:4ff615bf10e589799a96729fdf19df67dc8b5fb03090a934107074b5c09b5393:13495a29-65e6-4853-90b1-05bb4dba9040:__main__.process#3dbe5e02-a5e6-48b6-8cb8-e3f0447d7a40": "<[1.0,1.0]>",
            "urn:fz-juelich.de:alpaca:function_execution:Python:4ff615bf10e589799a96729fdf19df67dc8b5fb03090a934107074b5c09b5393:13495a29-65e6-4853-90b1-05bb4dba9040:__main__.process#6ef55dd9-35f5-4519-aed5-80906c7fa341": "<[4.0,4.0]>",
                        "urn:fz-juelich.de:alpaca:function_execution:Python:4ff615bf10e589799a96729fdf19df67dc8b5fb03090a934107074b5c09b5393:13495a29-65e6-4853-90b1-05bb4dba9040:__main__.process#7e3565c0-4313-4229-a0dc-8fa81e4301a1": "<[3.0,3.0]>",
                        "urn:fz-juelich.de:alpaca:function_execution:Python:4ff615bf10e589799a96729fdf19df67dc8b5fb03090a934107074b5c09b5393:13495a29-65e6-4853-90b1-05bb4dba9040:__main__.process#f635dbb8-ad01-4c3d-99ca-5496940143cc": "<[2.0,2.0]>",
                        "urn:fz-juelich.de:alpaca:object:Python:__main__.InputObject:84fa33edca00abb3c664c3b994e455ae10fbefa1": "<[2.0,2.0]>",
            "urn:fz-juelich.de:alpaca:object:Python:__main__.InputObject:9dbee0f2b42ba928138d4eb3cc3059f2d7086716": "<[4.0,4.0]>",
            "urn:fz-juelich.de:alpaca:object:Python:__main__.InputObject:b443853aa145342288afaae4f68b6b421683f411": "<[1.0,1.0]>",
            "urn:fz-juelich.de:alpaca:object:Python:__main__.InputObject:eed23509f67bfc5dd108fe361ce57a1b9737a286": "<[3.0,3.0]>",
        }
        graph = ProvenanceGraph(self.input_file)
        for node, time_interval in graph.graph.nodes(data='Time Interval'):
            self.assertEqual(time_interval, expected_intervals[node])

    def test_aggregation_without_intervals(self):
        graph = ProvenanceGraph(self.input_file, time_intervals=False)
        aggregated = graph.aggregate({})
        for _, attrs in aggregated.nodes(data=True):
            self.assertFalse("gephi_interval" in attrs)
            self.assertFalse("Time Interval" in attrs)


class GraphAggregationTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ttl_path = Path(__file__).parent / "res"
        input_file = cls.ttl_path / "parallel_graph.ttl"
        cls.graph = ProvenanceGraph(input_file, attributes=['shape',
                                                            'metadata', 'id'])
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

    def test_aggregation_by_callable(self):
        graph_file = self.ttl_path / "multiple_file_output.ttl"

        # Non-aggregated graph
        graph = ProvenanceGraph(graph_file)

        # Aggregate without attributes
        aggregated = graph.aggregate({}, output_file=None)

        # Aggregate separating by file path in File nodes
        aggregated_path = graph.aggregate({'File': ('File_path',)},
                                          output_file=None)

        # Aggregate using a callable to separate files which path starts with
        # "/outputs/"
        is_cut_plot = lambda g, n, d: d['File_path'].startswith("/outputs/")
        aggregated_callable = graph.aggregate({'File': (is_cut_plot,)},
                                              output_file=None)

        # Define a dictionary with the expected values for each case, that
        # are used in subtests below
        tests = {
            'non_aggregated': {'graph': graph.graph, 'length': 10,
                               'counts': {'InputObject': 3,
                                          'plot_function': 3,
                                          'cut_function': 1,
                                          'File': 3},
                               'paths': ["/full.png",
                                         "/outputs/1.png",
                                         "/outputs/2.png"]
                               },

            'aggregated': {'graph': aggregated, 'length': 5,
                           'counts': {'InputObject': 2,
                                      'plot_function': 1,
                                      'cut_function': 1,
                                      'File': 1},
                           'paths': "/full.png;/outputs/1.png;/outputs/2.png"
                           },

            'aggregated_path': {'graph': aggregated_path, 'length': 10,
                                'counts': {'InputObject': 3,
                                           'plot_function': 3,
                                           'cut_function': 1,
                                           'File': 3},
                                'paths': ["/full.png",
                                          "/outputs/1.png",
                                          "/outputs/2.png"]
                                },
            'aggregated_callable': {'graph': aggregated_callable, 'length': 7,
                                    'counts': {'InputObject': 2,
                                               'plot_function': 2,
                                               'cut_function': 1,
                                               'File': 2},
                                    'paths': ["/full.png",
                                              "/outputs/1.png;/outputs/2.png"]
                                    },
        }

        for key, expected in tests.items():
            with self.subTest(f"Graph {key}"):
                test_graph = expected['graph']
                nodes = test_graph.nodes
                self.assertEqual(len(nodes), expected['length'])

                # Check if node counts is as expected
                all_labels = [nodes[node]['label'] for node in nodes]
                counts = Counter(all_labels)
                for label, count in expected['counts'].items():
                    self.assertEqual(counts[label], count)

                # Check if file paths in the node are as expected
                paths = expected['paths']
                for node, attrs in nodes.items():
                    # Check value of file paths in File nodes
                    if attrs['label'] == "File":
                        if isinstance(paths, list):
                            self.assertTrue(attrs['File_path'] in paths)
                        else:
                            self.assertEqual(attrs['File_path'], paths)

    def test_aggregation_by_attribute_with_missing(self):
        aggregated = self.graph.aggregate({'InputObject': ('id',)},
                                          use_function_parameters=False,
                                          output_file=None)
        nodes = aggregated.nodes

        self.assertEqual(len(nodes), 5)

        expected_values_per_node = {
            'OutputObject': {'metadata': "0;1",
                             'shape': "(2,);(3,);(4,);(5,)"},
            'InputObject': {'metadata': "5",
                            'shape': ["(2,)", "(3,);(4,);(5,)"],
                            'id': ["1", None]},
            'process': {'process:value': "0;1;2;3"},
            'list': {}
        }

        all_labels = [nodes[node]['label'] for node in nodes]
        counts = Counter(all_labels)
        self.assertEqual(counts['OutputObject'], 1)
        self.assertEqual(counts['InputObject'], 2)
        self.assertEqual(counts['process'], 1)
        self.assertEqual(counts['list'], 1)

        for node, attrs in nodes.items():
            label = attrs['label']
            with self.subTest(f"Node label {label}"):
                self.assertTrue(label in expected_values_per_node)
                for key, value in expected_values_per_node[label].items():
                    attr_val = attrs[key] if key in attrs else None
                    if not isinstance(value, list):
                        self.assertEqual(attr_val, value)
                    else:
                        self.assertTrue(attr_val in value)

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

    def test_aggregation_member_info(self):
        aggregated = self.graph.aggregate({}, use_function_parameters=False,
                                          output_file=None)
        nodes = aggregated.nodes

        self.assertEqual(len(nodes), 4)

        expected = {
            'OutputObject': {'member_count': 4,
                             'members': "urn:fz-juelich.de:alpaca:object:Python:__main__.OutputObject:4ef19b49bcf029faae5349020a54096d53398c95;urn:fz-juelich.de:alpaca:object:Python:__main__.OutputObject:3934c99ea6197963f4bc7413932f6ce6dd800b08;urn:fz-juelich.de:alpaca:object:Python:__main__.OutputObject:93f4a32cb869a3e115e3382fd0fd49ab4ea0c8df;urn:fz-juelich.de:alpaca:object:Python:__main__.OutputObject:97ce94acf4ec4e2cb7d1319b798dbdd187df9558"},
            'InputObject': {'member_count': 4,
                            'members': "urn:fz-juelich.de:alpaca:object:Python:__main__.InputObject:84fa33edca00abb3c664c3b994e455ae10fbefa1;urn:fz-juelich.de:alpaca:object:Python:__main__.InputObject:9dbee0f2b42ba928138d4eb3cc3059f2d7086716;urn:fz-juelich.de:alpaca:object:Python:__main__.InputObject:eed23509f67bfc5dd108fe361ce57a1b9737a286;urn:fz-juelich.de:alpaca:object:Python:__main__.InputObject:b443853aa145342288afaae4f68b6b421683f411"},
            'process': {'member_count': 4,
                        'members': "urn:fz-juelich.de:alpaca:function_execution:Python:4ff615bf10e589799a96729fdf19df67dc8b5fb03090a934107074b5c09b5393:13495a29-65e6-4853-90b1-05bb4dba9040:__main__.process#6ef55dd9-35f5-4519-aed5-80906c7fa341;urn:fz-juelich.de:alpaca:function_execution:Python:4ff615bf10e589799a96729fdf19df67dc8b5fb03090a934107074b5c09b5393:13495a29-65e6-4853-90b1-05bb4dba9040:__main__.process#7e3565c0-4313-4229-a0dc-8fa81e4301a1;urn:fz-juelich.de:alpaca:function_execution:Python:4ff615bf10e589799a96729fdf19df67dc8b5fb03090a934107074b5c09b5393:13495a29-65e6-4853-90b1-05bb4dba9040:__main__.process#3dbe5e02-a5e6-48b6-8cb8-e3f0447d7a40;urn:fz-juelich.de:alpaca:function_execution:Python:4ff615bf10e589799a96729fdf19df67dc8b5fb03090a934107074b5c09b5393:13495a29-65e6-4853-90b1-05bb4dba9040:__main__.process#f635dbb8-ad01-4c3d-99ca-5496940143cc"},
            'list': {'member_count': 1,
                     'members': "urn:fz-juelich.de:alpaca:object:Python:builtins.list:f801594e5cebdc73ba8815e8ad66cab5cd86d2bf"}
        }

        for node, attrs in nodes.items():
            label = attrs['label']
            with self.subTest(f"Node label {label}"):
                expected_info = expected[label]
                self.assertTrue('members' in attrs)
                self.assertEqual(attrs['member_count'],
                                 expected_info['member_count'])
                graph_members = sorted(attrs['members'].split(";"))
                expected_members = sorted(expected_info['members'].split(";"))
                self.assertListEqual(graph_members, expected_members)

    def test_aggregation_member_info_count_only(self):
        aggregated = self.graph.aggregate({}, use_function_parameters=False,
                                          output_file=None,
                                          record_members=False)
        nodes = aggregated.nodes

        self.assertEqual(len(nodes), 4)

        expected_counts = {
            'OutputObject': 4,
            'InputObject': 4,
            'process': 4,
            'list': 1
        }

        for node, attrs in nodes.items():
            label = attrs['label']
            with self.subTest(f"Node label {label}"):
                self.assertTrue('members' not in attrs)
                self.assertEqual(attrs['member_count'], expected_counts[label])


class GraphMultipleSourcesTestCase(unittest.TestCase):
    @staticmethod
    def _node_comparison(attr_G1, attr_G2):
        # Functions will have different execution IDs and orders
        for ignored_attr in ('execution_id', 'execution_order'):
            for attr in (attr_G1, attr_G2):
                if ignored_attr in attr:
                    attr.pop(ignored_attr)

        return attr_G1 == attr_G2

    @classmethod
    def setUpClass(cls):
        ttl_path = Path(__file__).parent / "res"
        cls.single_graph = ttl_path / "single_graph.ttl"
        cls.multiple_graphs = [ttl_path / f"multi_graph_{i}.ttl"
                               for i in range(2)]
        alpaca_setting('authority', "my-authority")

    def test_multiple_sources(self):
        single_graph = ProvenanceGraph(self.single_graph,
                                       attributes='all',
                                       annotations='all',
                                       time_intervals=False)
        multiple_graph = ProvenanceGraph(*self.multiple_graphs,
                                         attributes='all',
                                         annotations='all',
                                         time_intervals=False)

        single_nx_graph = single_graph.graph
        multiple_nx_graph = multiple_graph.graph

        self.assertEqual(len(single_nx_graph.nodes), 8)
        self.assertEqual(len(multiple_nx_graph.nodes), 8)

        # All objects should be present and with the same data
        for data_node, data in single_graph.graph.nodes(data=True):
            if data['type'] == 'object':
                self.assertTrue(data_node in multiple_nx_graph.nodes)

        # Graphs should be equal, except for the function executions IDs and
        # order
        self.assertTrue(nx.is_isomorphic(single_nx_graph, multiple_nx_graph,
                                         node_match=self._node_comparison))


if __name__ == "__main__":
    unittest.main()
