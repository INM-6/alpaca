import unittest

from pathlib import Path
import tempfile
import rdflib
from rdflib.compare import graph_diff

import numpy as np
import quantities as pq
import neo

from alpaca.alpaca_types import (DataObject, File, FunctionInfo,
                                 FunctionExecution,
                                 Container)
from alpaca import AlpacaProvDocument, alpaca_setting
from alpaca.serialization.converters import _ensure_type
from alpaca.serialization.neo import _neo_to_prov

# Define tuples of information as they would be captured by the decorator
# The unit tests will build FunctionExecution tuples using them

# Function
TEST_FUNCTION = FunctionInfo("test_function", "test", "0.0.1")

# Object without metadata
INPUT = DataObject("12345", "joblib_SHA1", "test.InputObject", 12345, {}, None)

# Object with all main types of metadata
INPUT_METADATA = DataObject("12345", "joblib_SHA1", "test.InputObject", 12345,
                            details={'metadata_1': "value1",
                                     'metadata_2': 5,
                                     'metadata_3': 5.0,
                                     'metadata_4': True},
                            value=None)

OUTPUT_METADATA_NEO = DataObject("54321", "joblib_SHA1",
                                 "neo.core.SpikeTrain", 54321,
                                 details={'name': "Spiketrain#1",
                                          'annotations': {'sua': False,
                                                          'channel': 56},
                                          'array_annotations': {
                                              'complexity': np.array(
                                                  [0, 1, 2, 3]),
                                              'event': np.array(
                                                  [True, False, False])}
                                          },
                                 value=None)

# Object with special metadata

# Files
INPUT_FILE = File("56789", "sha256", "/test_file_input")
OUTPUT_FILE = File("98765", "sha256", "/test_file_output")

# Simple objects to test multiple inputs/outputs handling
INPUT_2 = DataObject("212345", "joblib_SHA1", "test.InputObject", 212345, {},
                     None)
OUTPUT = DataObject("54321", "joblib_SHA1", "test.OutputObject", 54321, {},
                    None)
OUTPUT_2 = DataObject("254321", "joblib_SHA1", "test.OutputObject", 254321, {},
                      None)

# None output
NONE_OUTPUT = DataObject("777777", "UUID", "builtins.NoneType", 777777, {},
                         None)

# Object collections
COLLECTION = DataObject("888888", "joblib_SHA1", "builtins.list", 888888, {},
                        None)

# General information. Will be fixed across the tests
TIMESTAMP_START = "2022-05-02T12:34:56.123456"
TIMESTAMP_END = "2022-05-02T12:35:56.123456"
SCRIPT_INFO = File("111111", "sha256", "/script.py")
SCRIPT_SESSION_ID = "999999"


def assert_rdf_graphs_equal(G1, G2):
    result = G1.isomorphic(G2)
    _, in_first, in_second = graph_diff(G1, G2)
    result = result and (len(in_first) == 0)
    result = result and (len(in_second) == 0)
    return result


class AlpacaProvSerializationTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ttl_path = Path(__file__).parent / "res"
        alpaca_setting('authority', "fz-juelich.de")

    def setUp(self):
        alpaca_setting('store_values', [])

    def test_value_serialization(self):
        # DataObject tuples for each type that should be captured
        # They are output of the simulated output
        alpaca_setting('store_values', ['builtins.dict'])

        INT = DataObject("543211", "joblib_SHA1", "builtins.int", 543211,
                         {}, 1)
        FLOAT = DataObject("543212", "joblib_SHA1", "builtins.float", 543212,
                           {}, 1.1)
        STR = DataObject("543213", "joblib_SHA1", "builtins.str", 543213,
                         {}, "test")
        COMPLEX = DataObject("543214", "joblib_SHA1", "builtins.complex",
                             543214, {}, 3+5j)
        BOOL = DataObject("543215", "joblib_SHA1", "builtins.bool", 543215,
                          {}, True)
        NUMPY_FLOAT32 = DataObject("543216", "joblib_SHA1", "numpy.float32",
                                   543216, {}, np.float32(1.2))
        NUMPY_FLOAT64 = DataObject("543217", "joblib_SHA1", "numpy.float64",
                                   543217, {}, np.float64(1.3))
        NUMPY_INT64 = DataObject("543218", "joblib_SHA1", "numpy.int64",
                                 543218, {}, np.int64(2))
        NUMPY_INT32 = DataObject("543219", "joblib_SHA1", "numpy.int32",
                                 543219, {}, np.int32(3))
        NUMPY_INT16 = DataObject("5432110", "joblib_SHA1", "numpy.int16",
                                 5432110, {}, np.int16(-4))

        DICT = DataObject("5432111", "joblib_SHA1", "builtins.dict",
                          5432111, {},
                          str(dict(id=[1, 2, 3], value={4, 5, 6})))

        function_execution = FunctionExecution(
            function=TEST_FUNCTION,
            input={'input_1': INPUT}, params={'param_1': 5},
            output={0: OUTPUT, 1: INT, 2: FLOAT, 3: STR, 4: COMPLEX,
                    5: BOOL, 6: NUMPY_FLOAT32, 7: NUMPY_FLOAT64,
                    8: NUMPY_INT64, 9: NUMPY_INT32, 10: NUMPY_INT16,
                    11: DICT},
            call_ast=None,
            arg_map=['input_1', 'param_1'], kwarg_map=[], return_targets=[],
            time_stamp_start=TIMESTAMP_START, time_stamp_end=TIMESTAMP_END,
            execution_id="12345", order=1,
            code_statement="test_function(input_1, 5)"
        )

        # Load expected RDF graph
        expected_graph_file = self.ttl_path / "values.ttl"
        expected_graph = rdflib.Graph()
        expected_graph.parse(expected_graph_file, format='turtle')

        # Serialize the history using AlpacaProv document
        alpaca_prov = AlpacaProvDocument()
        alpaca_prov.add_history(SCRIPT_INFO, SCRIPT_SESSION_ID,
                                history=[function_execution])

        # Check if graphs are equal
        self.assertTrue(assert_rdf_graphs_equal(alpaca_prov.graph,
                                                expected_graph))

    def test_input_output_serialization(self):
        function_execution = FunctionExecution(
            function=TEST_FUNCTION,
            input={'input_1': INPUT}, params={'param_1': 5},
            output={0: OUTPUT}, call_ast=None,
            arg_map=['input_1', 'param_1'], kwarg_map=[], return_targets=[],
            time_stamp_start=TIMESTAMP_START, time_stamp_end=TIMESTAMP_END,
            execution_id="12345", order=1,
            code_statement="test_function(input_1, 5)"
        )

        # Load expected RDF graph
        expected_graph_file = self.ttl_path / "input_output.ttl"
        expected_graph = rdflib.Graph()
        expected_graph.parse(expected_graph_file, format='turtle')

        # Serialize the history using AlpacaProv document
        alpaca_prov = AlpacaProvDocument()
        alpaca_prov.add_history(SCRIPT_INFO, SCRIPT_SESSION_ID,
                                history=[function_execution])

        # Check if graphs are equal
        self.assertTrue(assert_rdf_graphs_equal(alpaca_prov.graph,
                                                expected_graph))

    def test_metadata_serialization(self):
        function_execution = FunctionExecution(
            function=TEST_FUNCTION,
            input={'input_1': INPUT_METADATA}, params={'param_1': 5},
            output={0: OUTPUT_METADATA_NEO}, call_ast=None,
            arg_map=['input_1', 'param_1'], kwarg_map=[], return_targets=[],
            time_stamp_start=TIMESTAMP_START, time_stamp_end=TIMESTAMP_END,
            execution_id="12345", order=1,
            code_statement="test_function(input_1, 5)"
        )

        # Load expected RDF graph
        expected_graph_file = self.ttl_path / "metadata.ttl"
        expected_graph = rdflib.Graph()
        expected_graph.parse(expected_graph_file, format='turtle')

        # Serialize the history using AlpacaProv document
        alpaca_prov = AlpacaProvDocument()
        alpaca_prov.add_history(SCRIPT_INFO, SCRIPT_SESSION_ID,
                                history=[function_execution])

        # Check if graphs are equal
        self.assertTrue(assert_rdf_graphs_equal(alpaca_prov.graph,
                                                expected_graph))

    def test_input_container_serialization(self):
        function_execution = FunctionExecution(
            function=TEST_FUNCTION,
            input={'input_container': Container((INPUT, INPUT_2))},
            params={'param_1': 5},
            output={0: OUTPUT}, call_ast=None,
            arg_map=['input_container', 'param_1'], kwarg_map=[],
            return_targets=[],
            time_stamp_start=TIMESTAMP_START, time_stamp_end=TIMESTAMP_END,
            execution_id="12345", order=1,
            code_statement="test_function(input_container, 5)"
        )

        # Load expected RDF graph
        expected_graph_file = self.ttl_path / "input_container.ttl"
        expected_graph = rdflib.Graph()
        expected_graph.parse(expected_graph_file, format='turtle')

        # Serialize the history using AlpacaProv document
        alpaca_prov = AlpacaProvDocument()
        alpaca_prov.add_history(SCRIPT_INFO, SCRIPT_SESSION_ID,
                                history=[function_execution])

        # Check if graphs are equal
        self.assertTrue(assert_rdf_graphs_equal(alpaca_prov.graph,
                                                expected_graph))

    def test_class_method_serialization(self):
        obj_info = DataObject(
            hash="232323",
            hash_method="joblib_SHA1",
            type="test.ObjectWithMethod",
            id=232323,
            details={}, value=None)

        function_execution = FunctionExecution(
            function=FunctionInfo('ObjectWithMethod.process',
                                  'test', ''),
            input={'self': obj_info, 'array': INPUT},
            params={'param1': 4},
            output={0: OUTPUT}, call_ast=None,
            arg_map=['self', 'array', 'param1'], kwarg_map=[],
            return_targets=[],
            time_stamp_start=TIMESTAMP_START, time_stamp_end=TIMESTAMP_END,
            execution_id="12345", order=1,
            code_statement="res = obj.process(INPUT, 4)")

        # Load expected RDF graph
        expected_graph_file = self.ttl_path / "class_method.ttl"
        expected_graph = rdflib.Graph()
        expected_graph.parse(expected_graph_file, format='turtle')

        # Serialize the history using AlpacaProv document
        alpaca_prov = AlpacaProvDocument()
        alpaca_prov.add_history(SCRIPT_INFO, SCRIPT_SESSION_ID,
                                history=[function_execution])

        # Check if graphs are equal
        self.assertTrue(assert_rdf_graphs_equal(alpaca_prov.graph,
                                                expected_graph))

    def test_input_multiple_serialization(self):
        function_execution = FunctionExecution(
            function=TEST_FUNCTION,
            input={'input_1': INPUT, 'input_2': INPUT_2},
            params={'param_1': 5},
            output={0: OUTPUT}, call_ast=None,
            arg_map=['input_1', 'input_2', 'param_1'], kwarg_map=[],
            return_targets=[],
            time_stamp_start=TIMESTAMP_START, time_stamp_end=TIMESTAMP_END,
            execution_id="12345", order=1,
            code_statement="test_function(input_1, input_2, 5)"
        )

        # Load expected RDF graph
        expected_graph_file = self.ttl_path / "input_multiple.ttl"
        expected_graph = rdflib.Graph()
        expected_graph.parse(expected_graph_file, format='turtle')

        # Serialize the history using AlpacaProv document
        alpaca_prov = AlpacaProvDocument()
        alpaca_prov.add_history(SCRIPT_INFO, SCRIPT_SESSION_ID,
                                history=[function_execution])

        # Check if graphs are equal
        self.assertTrue(assert_rdf_graphs_equal(alpaca_prov.graph,
                                                expected_graph))

    def test_collection_serialization(self):
        indexing_access = FunctionExecution(
            function=FunctionInfo(name='subscript', module="", version=""),
            input={0: COLLECTION}, params={'index': 0},
            output={0: INPUT}, call_ast=None, arg_map=None, kwarg_map=None,
            return_targets=[], time_stamp_start=TIMESTAMP_START,
            time_stamp_end=TIMESTAMP_END, execution_id="888888", order=None,
            code_statement=None)

        function_execution = FunctionExecution(
            function=TEST_FUNCTION,
            input={'input_1': INPUT}, params={'param_1': 5},
            output={0: OUTPUT}, call_ast=None,
            arg_map=['input_1', 'param_1'], kwarg_map=[], return_targets=[],
            time_stamp_start=TIMESTAMP_START, time_stamp_end=TIMESTAMP_END,
            execution_id="12345", order=1,
            code_statement="test_function(source_list[0], 5)"
        )

        # Load expected RDF graph
        expected_graph_file = self.ttl_path / "collection.ttl"
        expected_graph = rdflib.Graph()
        expected_graph.parse(expected_graph_file, format='turtle')

        # Serialize the history using AlpacaProv document
        alpaca_prov = AlpacaProvDocument()
        alpaca_prov.add_history(SCRIPT_INFO, SCRIPT_SESSION_ID,
                                history=[indexing_access, function_execution])

        # Check if graphs are equal
        self.assertTrue(assert_rdf_graphs_equal(alpaca_prov.graph,
                                                expected_graph))

    def test_file_output_serialization(self):
        function_execution = FunctionExecution(
            function=TEST_FUNCTION,
            input={'input_1': INPUT}, params={'param_1': 5},
            output={0: NONE_OUTPUT, 'file.0': OUTPUT_FILE}, call_ast=None,
            arg_map=['input_1', 'param_1'], kwarg_map=[], return_targets=[],
            time_stamp_start=TIMESTAMP_START, time_stamp_end=TIMESTAMP_END,
            execution_id="12345", order=1,
            code_statement="test_function(input_1, 5)"
        )

        # Load expected RDF graph
        expected_graph_file = self.ttl_path / "file_output.ttl"
        expected_graph = rdflib.Graph()
        expected_graph.parse(expected_graph_file, format='turtle')

        # Serialize the history using AlpacaProv document
        alpaca_prov = AlpacaProvDocument()
        alpaca_prov.add_history(SCRIPT_INFO, SCRIPT_SESSION_ID,
                                history=[function_execution])

        # Check if graphs are equal
        self.assertTrue(assert_rdf_graphs_equal(alpaca_prov.graph,
                                                expected_graph))

    def test_file_input_serialization(self):
        function_execution = FunctionExecution(
            function=TEST_FUNCTION,
            input={'input_1': INPUT_FILE}, params={'param_1': 5},
            output={0: OUTPUT}, call_ast=None,
            arg_map=['input_1', 'param_1'], kwarg_map=[], return_targets=[],
            time_stamp_start=TIMESTAMP_START, time_stamp_end=TIMESTAMP_END,
            execution_id="12345", order=1,
            code_statement="test_function(input_1, 5)"
        )

        # Load expected RDF graph
        expected_graph_file = self.ttl_path / "file_input.ttl"
        expected_graph = rdflib.Graph()
        expected_graph.parse(expected_graph_file, format='turtle')

        # Serialize the history using AlpacaProv document
        alpaca_prov = AlpacaProvDocument()
        alpaca_prov.add_history(SCRIPT_INFO, SCRIPT_SESSION_ID,
                                history=[function_execution])

        # Check if graphs are equal
        self.assertTrue(assert_rdf_graphs_equal(alpaca_prov.graph,
                                                expected_graph))


class SerializationIOTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ttl_path = Path(__file__).parent / "res"
        cls.temp_dir = tempfile.TemporaryDirectory(dir=cls.ttl_path,
                                                   suffix="tmp")
        function_execution = FunctionExecution(
            function=TEST_FUNCTION,
            input={'input_1': INPUT}, params={'param_1': 5},
            output={0: OUTPUT}, call_ast=None,
            arg_map=['input_1'], kwarg_map=[], return_targets=[],
            time_stamp_start=TIMESTAMP_START, time_stamp_end=TIMESTAMP_END,
            execution_id="12345", order=1,
            code_statement="test_function(input_1, 5)"
        )

        # Serialize the history using AlpacaProv document
        cls.alpaca_prov = AlpacaProvDocument()
        cls.alpaca_prov.add_history(SCRIPT_INFO, SCRIPT_SESSION_ID,
                                    history=[function_execution])
        alpaca_setting('authority', "fz-juelich.de")

    def test_serialization_deserialization(self):

        # For every supported format, serialize to a temp file
        for output_format in ('json-ld', 'n3', 'nt', 'hext', 'pretty-xml',
                              'trig', 'turtle', 'longturtle', 'xml'):
            with self.subTest(f"Serialization format",
                              output_format=output_format):
                output_file = Path(
                    self.temp_dir.name) / f"test.{output_format}"
                self.alpaca_prov.serialize(output_file,
                                           file_format=output_format)
                self.assertTrue(output_file.exists())

        # For every supported format with parsers, read the temp saved files
        # and check against the original graph.
        # No parsers for: 'pretty-xml', 'longturtle', 'hext' and 'trig'
        for read_format in ('json-ld', 'n3', 'nt', 'turtle', 'xml'):
            with self.subTest(f"Deserialization format",
                              read_format=read_format):
                input_file = Path(self.temp_dir.name) / f"test.{read_format}"
                read_alpaca_prov = AlpacaProvDocument()
                read_alpaca_prov.read_records(input_file, file_format=None)
                self.assertTrue(assert_rdf_graphs_equal(self.alpaca_prov.graph,
                                                        read_alpaca_prov.graph))

        # Test unsupported formats
        for wrong_format in ('pretty-xml', 'longturtle', 'hext', 'trig'):
            with self.subTest(f"Unsupported format",
                              wrong_format=wrong_format):
                with self.assertRaises(ValueError):
                    input_file = Path(
                        self.temp_dir.name) / f"test.{wrong_format}"
                    read_alpaca_prov = AlpacaProvDocument()
                    read_alpaca_prov.read_records(input_file, file_format=None)

    def test_shortcut_format(self):
        input_ttl = self.ttl_path / "input_output.ttl"
        read_ttl = AlpacaProvDocument()
        read_ttl.read_records(input_ttl, file_format=None)
        self.assertTrue(assert_rdf_graphs_equal(read_ttl.graph,
                                                self.alpaca_prov.graph))

    def test_no_format(self):
        no_ext = Path(self.temp_dir.name) / "no_ext"
        self.alpaca_prov.serialize(no_ext, file_format='turtle')
        read_no_ext = AlpacaProvDocument()
        with self.assertRaises(ValueError):
            read_no_ext.read_records(no_ext, file_format=None)


class ConvertersTestCase(unittest.TestCase):

    def test_list(self):
        obj = [1, 2, 3]
        expected = "[1, 2, 3]"
        self.assertEqual(expected, _ensure_type(obj))

    def test_quantity(self):
        obj = 1 * pq.ms
        expected = "1.0 ms"
        self.assertEqual(expected, _ensure_type(obj))

    def test_neo(self):
        segment = neo.Segment(name="test")
        spiketrain = neo.SpikeTrain([1, 2, 3] * pq.ms, t_stop=10 * pq.ms)
        segment.spiketrains = [spiketrain]

        expected = "neo.core.segment.Segment(t_start=0.0 ms, " \
                   "t_stop=10.0 ms, name=test, description=None)"
        segment_str = _ensure_type(segment)
        self.assertEqual(expected, segment_str)

    def test_neo_selected_attributes(self):
        segment = neo.Segment(name="test")
        spiketrain = neo.SpikeTrain([1, 2, 3] * pq.ms, t_stop=10 * pq.ms)
        segment.spiketrains = [spiketrain]

        expected = "neo.core.segment.Segment(name=test, t_stop=10.0 ms)"
        segment_str = _neo_to_prov(segment, ['name', 't_stop'])
        self.assertEqual(expected, segment_str)

    def test_neo_single_attributes(self):
        segment = neo.Segment(name="test")

        expected = "neo.core.segment.Segment(name=test)"
        segment_str = _neo_to_prov(segment, ['name'])
        self.assertEqual(expected, segment_str)

    def test_base_types(self):
        self.assertEqual(True, _ensure_type(True))
        self.assertEqual(1, _ensure_type(1))
        self.assertEqual(1.56, _ensure_type(1.56))
        self.assertEqual("test", _ensure_type("test"))

    def test_others(self):
        value = 1.0 + 5.0j
        self.assertEqual("(1+5j)", _ensure_type(value))


class MultipleMembershipSerializationTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        alpaca_setting('authority', "fz-juelich.de")

    def test_multiple_memberships(self):
        # test relationship `super_container.containers[0].inputs[1]`
        self.ttl_path = Path(__file__).parent / "res"

        super_container = DataObject("2333333", "joblib_SHA1",
                                     "test.SuperContainer", 2333333, {}, None)

        super_container_list = DataObject("23333332", "joblib_SHA1",
                                          "builtins.list", 23333332, {}, None)

        container = DataObject("333333", "joblib_SHA1", "test.Container", 333333,
                               {}, None)

        container_list = DataObject("3333332", "joblib_SHA1", "builtins.list",
                                    3333332, {}, None)

        attribute_access_container = FunctionExecution(
            function=FunctionInfo(name='attribute', module="", version=""),
            input={0: super_container}, params={'name': 'containers'},
            output={0: super_container_list}, call_ast=None, arg_map=None,
            kwarg_map=None,
            return_targets=[], time_stamp_start=TIMESTAMP_START,
            time_stamp_end=TIMESTAMP_END, execution_id="888888",
            order=None, code_statement=None)

        indexing_access_container = FunctionExecution(
            function=FunctionInfo(name='subscript', module="", version=""),
            input={0: super_container_list}, params={'index': 0},
            output={0: container}, call_ast=None, arg_map=None, kwarg_map=None,
            return_targets=[], time_stamp_start=TIMESTAMP_START,
            time_stamp_end=TIMESTAMP_END, execution_id="2888888",
            order=None,
            code_statement=None)

        attribute_access_inputs = FunctionExecution(
            function=FunctionInfo(name='attribute', module="", version=""),
            input={0: container}, params={'name': 'inputs'},
            output={0: container_list}, call_ast=None, arg_map=None,
            kwarg_map=None,
            return_targets=[], time_stamp_start=TIMESTAMP_START,
            time_stamp_end=TIMESTAMP_END, execution_id="3888888",
            order=None, code_statement=None)

        indexing_access_inputs = FunctionExecution(
            function=FunctionInfo(name='subscript', module="", version=""),
            input={0: container_list}, params={'index': 1},
            output={0: INPUT}, call_ast=None, arg_map=None, kwarg_map=None,
            return_targets=[], time_stamp_start=TIMESTAMP_START,
            time_stamp_end=TIMESTAMP_END, execution_id="4888888",
            order=None,
            code_statement=None)

        function_execution = FunctionExecution(
            function=TEST_FUNCTION,
            input={'input_1': INPUT}, params={'param_1': 5},
            output={0: OUTPUT}, call_ast=None,
            arg_map=['input_1', 'param_1'], kwarg_map=[],
            return_targets=[],
            time_stamp_start=TIMESTAMP_START, time_stamp_end=TIMESTAMP_END,
            execution_id="12345", order=1,
            code_statement="test_function(super_container.containers[0].inputs[1], 5)"
        )

        # Load expected RDF graph
        expected_graph_file = self.ttl_path / "multiple_memberships.ttl"
        expected_graph = rdflib.Graph()
        expected_graph.parse(expected_graph_file, format='turtle')

        # Serialize the history using AlpacaProv document
        alpaca_prov = AlpacaProvDocument()
        alpaca_prov.add_history(SCRIPT_INFO, SCRIPT_SESSION_ID,
                                history=[attribute_access_container,
                                         indexing_access_container,
                                         attribute_access_inputs,
                                         indexing_access_inputs,
                                         function_execution])

        # Check if graphs are equal
        self.assertTrue(assert_rdf_graphs_equal(alpaca_prov.graph,
                                                expected_graph))


class NeoMetadataPluginTestCase(unittest.TestCase):
    pass


if __name__ == "__main__":
    unittest.main()
