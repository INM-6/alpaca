import unittest

from pathlib import Path
import tempfile
import rdflib
import numpy as np
import quantities as pq
import neo

from alpaca.alpaca_types import (DataObject, File, FunctionInfo,
                                 FunctionExecution,
                                 Container)
from alpaca import AlpacaProvDocument
from alpaca.serialization.converters import _ensure_type
from alpaca.serialization.neo import _neo_to_prov

# Define tuples of information as they would be captured by the decorator
# The unit tests will build FunctionExecution tuples using them

# Function
TEST_FUNCTION = FunctionInfo("test_function", "test", "0.0.1")

# Object without metadata
INPUT = DataObject("12345", "joblib", "test.InputObject", 12345, {})

# Object with all main types of metadata
INPUT_METADATA = DataObject("12345", "joblib", "test.InputObject", 12345,
                            details={'metadata_1': "value1",
                                     'metadata_2': 5,
                                     'metadata_3': 5.0,
                                     'metadata_4': True})

OUTPUT_METADATA_NEO = DataObject("54321", "joblib",
                                 "neo.core.SpikeTrain", 54321,
                                 details={'name': "Spiketrain#1",
                                          'annotations': {'sua': False,
                                                          'channel': 56},
                                          'array_annotations': {
                                              'complexity': np.array(
                                                  [0, 1, 2, 3]),
                                              'event': np.array(
                                                  [True, False, False])}
                                          })

# Object with special metadata

# Files
INPUT_FILE = File("56789", "sha256", "/test_file_input")
OUTPUT_FILE = File("98765", "sha256", "/test_file_output")

# Simple objects to test multiple inputs/outputs handling
INPUT_2 = DataObject("212345", "joblib", "test.InputObject", 212345, {})
OUTPUT = DataObject("54321", "joblib", "test.OutputObject", 54321, {})
OUTPUT_2 = DataObject("254321", "joblib", "test.OutputObject", 254321, {})

# Object collections
COLLECTION = DataObject("888888", "joblib", "builtins.list", 888888, {})

# General information. Will be fixed across the tests
TIMESTAMP_START = "2022-05-02T12:34:56.123456"
TIMESTAMP_END = "2022-05-02T12:35:56.123456"
SCRIPT_INFO = File("111111", "sha256", "/script.py")
SCRIPT_SESSION_ID = "999999"


class AlpacaProvSerializationTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ttl_path = Path(__file__).parent / "res"

    def test_input_output_serialization(self):
        function_execution = FunctionExecution(
            function=TEST_FUNCTION,
            input={'input_1': INPUT}, params={'param_1': 5},
            output={0: OUTPUT}, call_ast=None,
            arg_map=['input_1'], kwarg_map=[], return_targets=[],
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
        self.assertTrue(alpaca_prov.graph.isomorphic(expected_graph))

    def test_metadata_serialization(self):
        function_execution = FunctionExecution(
            function=TEST_FUNCTION,
            input={'input_1': INPUT_METADATA}, params={'param_1': 5},
            output={0: OUTPUT_METADATA_NEO}, call_ast=None,
            arg_map=['input_1'], kwarg_map=[], return_targets=[],
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
        self.assertTrue(alpaca_prov.graph.isomorphic(expected_graph))

    def test_input_container_serialization(self):
        function_execution = FunctionExecution(
            function=TEST_FUNCTION,
            input={'input_container': Container((INPUT, INPUT_2))},
            params={'param_1': 5},
            output={0: OUTPUT}, call_ast=None,
            arg_map=['input_container'], kwarg_map=[], return_targets=[],
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
        self.assertTrue(alpaca_prov.graph.isomorphic(expected_graph))

    def test_input_multiple_serialization(self):
        function_execution = FunctionExecution(
            function=TEST_FUNCTION,
            input={'input_1': INPUT, 'input_2': INPUT_2},
            params={'param_1': 5},
            output={0: OUTPUT}, call_ast=None,
            arg_map=['input_1', 'input_2'], kwarg_map=[], return_targets=[],
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
        self.assertTrue(alpaca_prov.graph.isomorphic(expected_graph))

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
            arg_map=['input_1'], kwarg_map=[], return_targets=[],
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
        self.assertTrue(alpaca_prov.graph.isomorphic(expected_graph))

    def test_file_output_serialization(self):
        function_execution = FunctionExecution(
            function=TEST_FUNCTION,
            input={'input_1': INPUT}, params={'param_1': 5},
            output={0: OUTPUT_FILE}, call_ast=None,
            arg_map=['input_1'], kwarg_map=[], return_targets=[],
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
        self.assertTrue(alpaca_prov.graph.isomorphic(expected_graph))

    def test_file_input_serialization(self):
        function_execution = FunctionExecution(
            function=TEST_FUNCTION,
            input={'input_1': INPUT_FILE}, params={'param_1': 5},
            output={0: OUTPUT}, call_ast=None,
            arg_map=['input_1'], kwarg_map=[], return_targets=[],
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
        self.assertTrue(alpaca_prov.graph.isomorphic(expected_graph))


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
                self.assertTrue(
                    self.alpaca_prov.graph.isomorphic(read_alpaca_prov.graph))

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
        self.assertTrue(read_ttl.graph.isomorphic(self.alpaca_prov.graph))

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


class NeoMetadataPluginTestCase(unittest.TestCase):
    pass


if __name__ == "__main__":
    unittest.main()