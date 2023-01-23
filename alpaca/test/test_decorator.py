import unittest

import joblib
import datetime
import sys
from io import StringIO
import tempfile
from pathlib import Path

import rdflib
from rdflib.compare import graph_diff

import numpy as np

from alpaca import (Provenance, activate, deactivate, save_provenance,
                    print_history)
from alpaca.alpaca_types import (FunctionInfo, Container, DataObject, File)

# Define some data and expected values test tracking

TEST_ARRAY = np.array([1, 2, 3])
TEST_ARRAY_INFO = DataObject(hash=joblib.hash(TEST_ARRAY, hash_name='sha1'),
                             hash_method="joblib_SHA1",
                             type="numpy.ndarray", id=id(TEST_ARRAY),
                             details={'shape': (3,), 'dtype': np.int64})

TEST_ARRAY_2 = np.array([4, 5, 6])
TEST_ARRAY_2_INFO = DataObject(hash=joblib.hash(TEST_ARRAY_2,
                                                hash_name='sha1'),
                               hash_method="joblib_SHA1",
                               type="numpy.ndarray", id=id(TEST_ARRAY_2),
                               details={'shape': (3,), 'dtype': np.int64})

CONTAINER = [TEST_ARRAY, TEST_ARRAY_2]


# Define some functions to test tracking in different scenarios

@Provenance(inputs=['array'])
def simple_function(array, param1, param2):
    """ Takes a single input and outputs a single element"""
    return array + 3


@Provenance(inputs=['array'])
def simple_function_default(array, param1, param2=10):
    """ Takes a single input and outputs a single element.
    One kwarg is default
    """
    return array + 5


@Provenance(inputs=None, container_input=['arrays'])
def container_input_function(arrays, param1, param2):
    """ Takes a container input (e.g. list) and outputs a single element"""
    return np.mean(arrays)


@Provenance(inputs=['arrays'])
def varargs_function(*arrays, param1, param2):
    """ Takes a variable argument input and outputs a single element"""
    return np.mean(arrays)


@Provenance(inputs=['array'])
def multiple_outputs_function(array, param1, param2):
    """ Takes a single input and outputs multiple elements as a tuple"""
    return array + 3, array + 4


@Provenance(inputs=['array_1', 'array_2'])
def multiple_inputs_function(array_1, array_2, param1, param2):
    """ Takes multiple inputs and outputs a single element"""
    return array_1 + array_2


@Provenance(inputs=['array'], container_output=True)
def container_output_function(array, param1, param2):
    """ Takes a single input and outputs multiple elements in a container"""
    return [array + i for i in range(3, 5)]


# Function to help verifying FunctionExecution tuples
def _check_function_execution(actual, exp_function, exp_input, exp_params,
                              exp_output, exp_arg_map, exp_kwarg_map,
                              exp_code_stmnt, exp_return_targets, exp_order,
                              test_case):
    # Check function
    test_case.assertTupleEqual(actual.function, exp_function)

    # Check inputs
    for input_arg, value in actual.input.items():
        test_case.assertTrue(input_arg in exp_input)
        test_case.assertTupleEqual(value, exp_input[input_arg])

    # Check parameters
    test_case.assertDictEqual(actual.params, exp_params)

    # Check outputs
    for output, value in actual.output.items():
        test_case.assertTrue(output in exp_output)
        test_case.assertTupleEqual(value, exp_output[output])

    # Check args and kwargs
    test_case.assertListEqual(actual.arg_map, exp_arg_map)
    test_case.assertListEqual(actual.kwarg_map, exp_kwarg_map)

    # Check other information
    test_case.assertEqual(actual.code_statement, exp_code_stmnt)
    test_case.assertListEqual(actual.return_targets, exp_return_targets)
    test_case.assertEqual(actual.order, exp_order)
    test_case.assertNotEqual(actual.execution_id, "")

    # Check time stamps are valid ISO dates
    test_case.assertIsInstance(
        datetime.datetime.fromisoformat(actual.time_stamp_start),
        datetime.datetime)
    test_case.assertIsInstance(
        datetime.datetime.fromisoformat(actual.time_stamp_end),
        datetime.datetime)


class ProvenanceDecoratorInterfaceFunctionsTestCase(unittest.TestCase):

    def test_activate_deactivate(self):
        activate(clear=True)
        simple_function(TEST_ARRAY, 1, 2)
        simple_function(TEST_ARRAY, 3, 4)
        deactivate()
        simple_function(TEST_ARRAY, 5, 6)

        self.assertEqual(len(Provenance.history), 2)
        self.assertEqual(Provenance.history[0].code_statement,
                         "simple_function(TEST_ARRAY, 1, 2)")
        self.assertEqual(Provenance.history[1].code_statement,
                         "simple_function(TEST_ARRAY, 3, 4)")

    def test_save_provenance(self):
        activate(clear=True)
        res = simple_function(TEST_ARRAY, 1, 2)
        deactivate()

        # For every supported format, serialize to a string
        for output_format in ('json-ld', 'n3', 'nt', 'hext', 'pretty-xml',
                              'trig', 'turtle', 'longturtle', 'xml'):
            with self.subTest(f"Serialization format",
                              output_format=output_format):
                serialization = save_provenance(file_name=None,
                                                file_format=output_format)
                self.assertNotEqual(serialization, "")

        # For shortucts, test the expected serializations
        for short_output_format, output_format in (('ttl', 'turtle'),
                                                   ('rdf', 'xml'),
                                                   ('json', 'json-ld')):
            with self.subTest(f"Short serialization format",
                              short_format=short_output_format):
                short = save_provenance(None, file_format=short_output_format)
                serialization = save_provenance(None, file_format=output_format)

                short_graph = rdflib.Graph()
                short_graph.parse(StringIO(short), format=output_format)

                serialization_graph = rdflib.Graph()
                serialization_graph.parse(StringIO(serialization),
                                          format=output_format)

                self.assertTrue(short_graph.isomorphic(serialization_graph))
                _, in_first, in_second = graph_diff(short_graph,
                                                    serialization_graph)
                self.assertEqual(len(in_first), 0)
                self.assertEqual(len(in_second), 0)

    def test_print_history(self):
        activate(clear=True)
        res = simple_function(TEST_ARRAY, 1, 2)
        deactivate()

        expected_str = str(Provenance.history)

        # Capture STDOUT and print
        captured = StringIO()
        sys.stdout = captured
        print_history()
        sys.stdout = sys.__stdout__

        self.assertEqual(captured.getvalue().replace("\n", ""), expected_str)


class ProvenanceDecoratorFunctionsTestCase(unittest.TestCase):

    def test_get_module_version(self):
        expected_numpy_version = np.__version__

        numpy_version = Provenance._get_module_version("numpy", "mean")
        self.assertEqual(numpy_version, expected_numpy_version)

        numpy_version_submodule = Provenance._get_module_version(
            "numpy.random", "normal")
        self.assertEqual(numpy_version_submodule, expected_numpy_version)

        main_version = Provenance._get_module_version("__main__",
                                                      "test_function")
        self.assertEqual(main_version, "")

        invalid = Provenance._get_module_version("non_existent", "test")
        self.assertEqual(invalid, "")


class ProvenanceDecoratorInputOutputCombinationsTestCase(unittest.TestCase):

    def test_simple_function(self):
        activate(clear=True)
        res = simple_function(TEST_ARRAY, 1, 2)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)

        expected_output = DataObject(
            hash=joblib.hash(TEST_ARRAY+3, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res),
            details={'shape': (3,), 'dtype': np.int64})

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('simple_function',
                                      'test_decorator', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={'param1': 1, 'param2': 2},
            exp_output={0: expected_output},
            exp_arg_map=['array', 'param1', 'param2'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = simple_function(TEST_ARRAY, 1, 2)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_simple_function_no_target(self):
        activate(clear=True)
        simple_function(TEST_ARRAY, param2=1, param1=2)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)

        # In this test we cannot know the id of the output, as it is not
        # stored in any variable. Let's get it from the history so that the
        # test does not fail
        output_id = Provenance.history[0].output[0].id

        expected_output = DataObject(
            hash=joblib.hash(TEST_ARRAY+3, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=output_id,
            details={'shape': (3,), 'dtype': np.int64})

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('simple_function',
                                      'test_decorator', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={'param1': 2, 'param2': 1},
            exp_output={0: expected_output},
            exp_arg_map=['array'],
            exp_kwarg_map=['param1', 'param2'],
            exp_code_stmnt="simple_function(TEST_ARRAY, param2=1, param1=2)",
            exp_return_targets=[],
            exp_order=1,
            test_case=self)

    def test_kwargs_params(self):
        activate(clear=True)
        res = simple_function(TEST_ARRAY, 1, param2=2)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)

        expected_output = DataObject(
            hash=joblib.hash(TEST_ARRAY+3, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res),
            details={'shape': (3,), 'dtype': np.int64})

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('simple_function',
                                      'test_decorator', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={'param1': 1, 'param2': 2},
            exp_output={0: expected_output},
            exp_arg_map=['array', 'param1'],
            exp_kwarg_map=['param2'],
            exp_code_stmnt="res = simple_function(TEST_ARRAY, 1, param2=2)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_kwargs_params_default(self):
        activate(clear=True)
        res = simple_function_default(TEST_ARRAY, 1)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)

        expected_output = DataObject(
            hash=joblib.hash(TEST_ARRAY+5, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res),
            details={'shape': (3,), 'dtype': np.int64})

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('simple_function_default',
                                      'test_decorator', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={'param1': 1, 'param2': 10},
            exp_output={0: expected_output},
            exp_arg_map=['array', 'param1'],
            exp_kwarg_map=['param2'],
            exp_code_stmnt="res = simple_function_default(TEST_ARRAY, 1)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_kwargs_params_default_override(self):
        activate(clear=True)
        res = simple_function_default(TEST_ARRAY, 1, 8)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)

        expected_output = DataObject(
            hash=joblib.hash(TEST_ARRAY+5, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res),
            details={'shape': (3,), 'dtype': np.int64})

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('simple_function_default',
                                      'test_decorator', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={'param1': 1, 'param2': 8},
            exp_output={0: expected_output},
            exp_arg_map=['array', 'param1', 'param2'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = simple_function_default(TEST_ARRAY, 1, 8)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_container_input_function(self):
        activate(clear=True)
        avg = container_input_function(CONTAINER, 3, 6)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)
        self.assertEqual(avg, 3.5)

        expected_output = DataObject(
            hash=joblib.hash(np.float64(3.5), hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.float64", id=id(avg),
            details={'shape': (), 'dtype': np.float64})

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('container_input_function',
                                      'test_decorator', ''),
            exp_input={'arrays': Container(tuple(
                [TEST_ARRAY_INFO, TEST_ARRAY_2_INFO]))},
            exp_params={'param1': 3, 'param2': 6},
            exp_output={0: expected_output},
            exp_arg_map=['arrays', 'param1', 'param2'],
            exp_kwarg_map=[],
            exp_code_stmnt="avg = container_input_function(CONTAINER, 3, 6)",
            exp_return_targets=['avg'],
            exp_order=1,
            test_case=self)

    def test_varargs_input_function(self):
        activate(clear=True)
        avg = varargs_function(*CONTAINER, param1=1, param2=2)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)
        self.assertEqual(avg, 3.5)

        expected_output = DataObject(
            hash=joblib.hash(np.float64(3.5), hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.float64", id=id(avg),
            details={'shape': (), 'dtype': np.float64})

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('varargs_function',
                                      'test_decorator', ''),
            exp_input={'arrays': Container(tuple(
                [TEST_ARRAY_INFO, TEST_ARRAY_2_INFO]))},
            exp_params={'param1': 1, 'param2': 2},
            exp_output={0: expected_output},
            exp_arg_map=['arrays'],
            exp_kwarg_map=['param1', 'param2'],
            exp_code_stmnt="avg = varargs_function(*CONTAINER, param1=1, param2=2)",
            exp_return_targets=['avg'],
            exp_order=1,
            test_case=self)

    def test_multiple_inputs_function(self):
        activate(clear=True)
        res = multiple_inputs_function(TEST_ARRAY, TEST_ARRAY_2, 3, 6)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)

        expected_output = DataObject(
            hash=joblib.hash(TEST_ARRAY+TEST_ARRAY_2, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res),
            details={'shape': (3,), 'dtype': np.int64})

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('multiple_inputs_function',
                                      'test_decorator', ''),
            exp_input={'array_1': TEST_ARRAY_INFO,
                       'array_2': TEST_ARRAY_2_INFO},
            exp_params={'param1': 3, 'param2': 6},
            exp_output={0: expected_output},
            exp_arg_map=['array_1', 'array_2', 'param1', 'param2'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = multiple_inputs_function(TEST_ARRAY, TEST_ARRAY_2, 3, 6)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_multiple_outputs_function_elements(self):
        activate(clear=True)
        res1, res2 = multiple_outputs_function(TEST_ARRAY, 3, 6)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)

        expected_output_1 = DataObject(
            hash=joblib.hash(TEST_ARRAY+3, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res1),
            details={'shape': (3,), 'dtype': np.int64})

        expected_output_2 = DataObject(
            hash=joblib.hash(TEST_ARRAY+4, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res2),
            details={'shape': (3,), 'dtype': np.int64})

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('multiple_outputs_function',
                                      'test_decorator', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={'param1': 3, 'param2': 6},
            exp_output={0: expected_output_1, 1: expected_output_2},
            exp_arg_map=['array', 'param1', 'param2'],
            exp_kwarg_map=[],
            exp_code_stmnt="res1, res2 = multiple_outputs_function(TEST_ARRAY, 3, 6)",
            exp_return_targets=['res1', 'res2'],
            exp_order=1,
            test_case=self)

    def test_multiple_outputs_function_tuple(self):
        activate(clear=True)
        res = multiple_outputs_function(TEST_ARRAY, 3, 6)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)

        expected_output = DataObject(
            hash=joblib.hash((TEST_ARRAY+3, TEST_ARRAY+4), hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="builtins.tuple", id=id(res),
            details={})

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('multiple_outputs_function',
                                      'test_decorator', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={'param1': 3, 'param2': 6},
            exp_output={0: expected_output},
            exp_arg_map=['array', 'param1', 'param2'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = multiple_outputs_function(TEST_ARRAY, 3, 6)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_container_output_function(self):
        activate(clear=True)
        res = container_output_function(TEST_ARRAY, 3, 6)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)

        expected_output_1 = DataObject(
            hash=joblib.hash(TEST_ARRAY + 3, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res[0]),
            details={'shape': (3,), 'dtype': np.int64})

        expected_output_2 = DataObject(
            hash=joblib.hash(TEST_ARRAY + 4, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res[1]),
            details={'shape': (3,), 'dtype': np.int64})

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('container_output_function',
                                      'test_decorator', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={'param1': 3, 'param2': 6},
            exp_output={0: expected_output_1, 1: expected_output_2},
            exp_arg_map=['array', 'param1', 'param2'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = container_output_function(TEST_ARRAY, 3, 6)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

@Provenance(inputs=None, file_input=['file_name'])
def extract_words_from_file(file_name):
    with open(file_name, "r") as input_file:
        words = input_file.read().split(" ")
    return words


@Provenance(inputs=['words'], file_output=['file_name'])
def save_words_to_file(words, file_name):
    with open(file_name, "w") as output_file:
        output_file.writelines(" ".join(words))


class ProvenanceDecoratorFileInputOutputTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.res_path = Path(__file__).parent.absolute() / "res"

    def test_file_input(self):
        activate(clear=True)
        file_name = self.res_path / "file_input.txt"
        res = extract_words_from_file(file_name)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)

        expected_list = ["This", "is", "an", "example", "file", "used", "as",
                         "input", "for", "the", "tests."]
        expected_output = DataObject(
            hash=joblib.hash(expected_list, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="builtins.list", id=id(res), details={})

        expected_file = File("96ccc1380e069667069acecea3e2ab559441657807e0a86d14f49028710ddb3a",
                             hash_type="sha256", path=file_name)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('extract_words_from_file',
                                      'test_decorator', ''),
            exp_input={'file_name': expected_file},
            exp_params={},
            exp_output={0: expected_output},
            exp_arg_map=['file_name'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = extract_words_from_file(file_name)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_file_output(self):
        activate(clear=True)
        tmp_file = tempfile.NamedTemporaryFile(dir=self.res_path, delete=True)
        file_name = tmp_file.name
        input_list = ["Some", "words", "were", "written", "to", "this", "file"]
        res = save_words_to_file(input_list, file_name)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)

        expected_input = DataObject(
            hash=joblib.hash(input_list, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="builtins.list", id=id(input_list), details={})

        # As None has its own UUID, let's get what was generated
        self.assertEqual(len(Provenance.history), 1)
        output_uuid = Provenance.history[0].output[0].hash

        expected_none_output = DataObject(hash=output_uuid, hash_method="UUID",
            type="builtins.NoneType", id=id(res), details={})

        expected_file = File("00d20b4831b0dadded2c633bdfc3dde3926fc17baaed51dacdab3e52a3b0d419",
                             hash_type="sha256", path=Path(file_name))

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('save_words_to_file',
                                      'test_decorator', ''),
            exp_input={'words': expected_input},
            exp_params={},
            exp_output={0: expected_none_output, 'file.0': expected_file},
            exp_arg_map=['words', 'file_name'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = save_words_to_file(input_list, file_name)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)


# Tracking methods inside classes
class ObjectWithMethod(object):
    def __init__(self, coefficient):
        self.coefficient = coefficient

    def process(self, array, param1, param2):
        return array + self.coefficient


ObjectWithMethod.process = Provenance(inputs=['self', 'array'])(
    ObjectWithMethod.process)


class ProvenanceDecoratorClassMethodsTestCase(unittest.TestCase):

    def test_class_method(self):
        activate(clear=True)
        obj = ObjectWithMethod(2)
        res = obj.process(TEST_ARRAY, 4, 5)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)

        obj_info = DataObject(
            hash=joblib.hash(obj, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="test_decorator.ObjectWithMethod",
            id=id(obj),
            details={'coefficient': 2})

        expected_output = DataObject(
            hash=joblib.hash(TEST_ARRAY+2, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res),
            details={'shape': (3,), 'dtype': np.int64})

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('ObjectWithMethod.process',
                                      'test_decorator', ''),
            exp_input={'self': obj_info, 'array': TEST_ARRAY_INFO},
            exp_params={'param1': 4, 'param2': 5},
            exp_output={0: expected_output},
            exp_arg_map=['self', 'array', 'param1', 'param2'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = obj.process(TEST_ARRAY, 4, 5)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)


if __name__ == "__main__":
    unittest.main()
