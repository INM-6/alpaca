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
import quantities as pq
import neo

from alpaca import (Provenance, activate, deactivate, save_provenance,
                    print_history, alpaca_setting)
from alpaca.alpaca_types import (FunctionInfo, Container, DataObject, File)

# Define some data and expected values test tracking

TEST_ARRAY = np.array([1, 2, 3])
TEST_ARRAY_INFO = DataObject(hash=joblib.hash(TEST_ARRAY, hash_name='sha1'),
                             hash_method="joblib_SHA1",
                             type="numpy.ndarray", id=id(TEST_ARRAY),
                             details={'shape': (3,), 'dtype': np.int64},
                             value=None)

TEST_ARRAY_2 = np.array([4, 5, 6])
TEST_ARRAY_2_INFO = DataObject(hash=joblib.hash(TEST_ARRAY_2,
                                                hash_name='sha1'),
                               hash_method="joblib_SHA1",
                               type="numpy.ndarray", id=id(TEST_ARRAY_2),
                               details={'shape': (3,), 'dtype': np.int64},
                               value=None)

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
    """
    Takes a single input and outputs multiple elements in a container.
    This function will have as tracked outputs all elements inside the first
    level, i.e., the two NumPy arrays.
    """
    return [array + i for i in range(3, 5)]


@Provenance(inputs=['array'], container_output=0)
def container_output_function_level_0(array, param1, param2):
    """
    Takes a single input and outputs multiple elements in a container.
    This function will have as tracked output the return list.
    Additional nodes from the list to each element inside the first level
    (i.e., the two NumPy arrays) will be added.
    """
    return [array + i for i in range(7, 9)]


@Provenance(inputs=['array'], container_output=1)
def container_output_function_level_1(array, param1, param2):
    """
    Takes a single input and outputs multiple elements in a container.
    This function will have as tracked output the return list.
    Additional nodes from the list to each element inside the first level
    (i.e., the two NumPy arrays) and from each array to all its elements
    (i.e., the integers in the second level) will be added.
    """
    return [array + i for i in range(2, 4)]


@Provenance(inputs=['array'], container_output=(0, 0))
def container_output_function_level_range_0_0(array, param1, param2):
    """
    Takes a single input and outputs multiple elements in a container.
    As we are requesting to track from output level zero to zero, this
    function will have as tracked output the return list. Additional nodes
    from the list to each element inside the first level
    (i.e., the two NumPy arrays) will be added.
    """
    return [array + i for i in range(1, 3)]


@Provenance(inputs=['array'], container_output=(0, 1))
def container_output_function_level_range_0_1(array, param1, param2):
    """
    Takes a single input and outputs multiple elements in a container.
    As we are requesting to track from output level zero to one, this function
    will have as tracked output the return list. Additional nodes from the
    list to each element inside the first level (i.e., the two NumPy arrays)
    and from each array to all its elements (i.e., the integers in the second
    level) will be added.
    """
    return [array + i for i in range(5, 7)]


@Provenance(inputs=['array'], container_output=(1, 1))
def container_output_function_level_range_1_1(array, param1, param2):
    """
    Takes a single input and outputs multiple elements in a container.
    As we are requesting to track from output level one to one, this function
    will have as tracked outputs all elements inside the first
    level, i.e., the two NumPy arrays. Additional nodes each array to all
    its elements (i.e., the integers in the second level) will be added.
    This option skips adding an output node for the first level, i.e., the
    list that contains the two arrays.
    """
    return [array + i for i in range(4, 6)]


@Provenance(inputs=['array'], container_output=True)
def dict_output_function(array, param1, param2):
    """ Takes as single input and outputs multiple elements in a dictionary """
    return {f"key.{i}": array + i + 3 for i in range(0, 2)}


@Provenance(inputs=['array'], container_output=1)
def dict_output_function_level(array, param1, param2):
    """ Takes as single input and outputs multiple elements in a dictionary """
    return {f"key.{i}": array + i + 3 for i in range(0, 2)}


class NonIterableContainer(object):

    def __init__(self, start):
        self.data = np.arange(start, start+3)

    def __getitem__(self, item):
        return  self.data[item]


@Provenance(inputs=[], container_output=0)
def non_iterable_container_output(param1):
    return NonIterableContainer(param1)


@Provenance(inputs=[])
def comprehension_function(param):
    return np.float64(param)


class NonIterableContainerOutputObject(object):
    def __init__(self, start):
        self._data = np.arange(start+1, start+4)

    def __getitem__(self, item):
        return  self._data[item]


NonIterableContainerOutputObject.__init__ = \
    Provenance(inputs=[], container_output=0)(NonIterableContainerOutputObject.__init__)


# Function to help verifying FunctionExecution tuples
def _check_function_execution(actual, exp_function, exp_input, exp_params,
                              exp_output, exp_arg_map, exp_kwarg_map,
                              exp_code_stmnt, exp_return_targets, exp_order,
                              test_case):
    # Check function
    test_case.assertTupleEqual(actual.function, exp_function)

    # Check inputs
    for input_arg, value in exp_input.items():
        test_case.assertTrue(input_arg in actual.input)
        actual_input = actual.input[input_arg]
        for attr in value._fields:
            actual_value = getattr(actual_input, attr)
            exp_value = getattr(value, attr)
            if attr != 'id' or (attr == 'id' and exp_value is not None):
                test_case.assertEqual(actual_value, exp_value)

    # Check parameters
    test_case.assertDictEqual(actual.params, exp_params)

    # Check outputs
    for output, value in exp_output.items():
        test_case.assertTrue(output in actual.output)
        actual_output = actual.output[output]
        for attr in value._fields:
            actual_value = getattr(actual_output, attr)
            exp_value = getattr(value, attr)
            if attr != 'id' or (attr == 'id' and exp_value is not None):
                test_case.assertEqual(actual_value, exp_value)

    # Check args and kwargs
    if actual.arg_map is not None:
        test_case.assertListEqual(actual.arg_map, exp_arg_map)
    else:
        test_case.assertIsNone(exp_arg_map)

    if actual.kwarg_map is not None:
        test_case.assertListEqual(actual.kwarg_map, exp_kwarg_map)
    else:
        test_case.assertIsNone(exp_kwarg_map)

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

    def test_save_provenance_show_progress(self):
        activate(clear=True)
        res = simple_function(TEST_ARRAY, 1, 2)
        deactivate()

        # Capture STDERR and serialize
        captured = StringIO()
        sys.stderr = captured
        save_provenance(file_name=None, show_progress=True)
        sys.stderr = sys.__stderr__

        captured_stderr = captured.getvalue()

        self.assertTrue("Serializing provenance history: 100%" in
                        captured_stderr)

    def test_save_provenance_no_progress(self):
        activate(clear=True)
        res = simple_function(TEST_ARRAY, 1, 2)
        deactivate()

        # Capture STDERR and serialize
        captured = StringIO()
        sys.stderr = captured
        save_provenance(file_name=None)
        sys.stderr = sys.__stderr__

        captured_stderr = captured.getvalue()

        self.assertEqual(captured_stderr, "")

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

    def test_save_provenance_no_capture(self):
        Provenance.clear()
        res = simple_function(TEST_ARRAY, 1, 2)

        serialization = save_provenance(None, file_format='turtle')
        self.assertIsNone(serialization)

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

        numpy_version = Provenance._get_module_version("numpy")
        self.assertEqual(numpy_version, expected_numpy_version)

        numpy_version_submodule = Provenance._get_module_version(
            "numpy.random")
        self.assertEqual(numpy_version_submodule, expected_numpy_version)

        main_version = Provenance._get_module_version("__main__")
        self.assertEqual(main_version, "")

        invalid = Provenance._get_module_version("non_existent")
        self.assertEqual(invalid, "")

        none = Provenance._get_module_version(None)
        self.assertEqual(none, "")


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
            details={'shape': (3,), 'dtype': np.int64}, value=None)

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
            details={'shape': (3,), 'dtype': np.int64}, value=None)

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
            details={'shape': (3,), 'dtype': np.int64}, value=None)

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
            details={'shape': (3,), 'dtype': np.int64}, value=None)

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
            details={'shape': (3,), 'dtype': np.int64}, value=None)

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
            details={'shape': (), 'dtype': np.float64}, value=3.5)

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
            details={'shape': (), 'dtype': np.float64}, value=3.5)

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
            details={'shape': (3,), 'dtype': np.int64}, value=None)

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
            details={'shape': (3,), 'dtype': np.int64}, value=None)

        expected_output_2 = DataObject(
            hash=joblib.hash(TEST_ARRAY+4, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res2),
            details={'shape': (3,), 'dtype': np.int64}, value=None)

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
            details={}, value=None)

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
            details={'shape': (3,), 'dtype': np.int64}, value=None)

        expected_output_2 = DataObject(
            hash=joblib.hash(TEST_ARRAY + 4, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res[1]),
            details={'shape': (3,), 'dtype': np.int64}, value=None)

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

    def test_container_output_function_level_0(self):
        activate(clear=True)
        res = container_output_function_level_0(TEST_ARRAY, 3, 6)
        deactivate()

        self.assertEqual(len(Provenance.history), 3)

        expected_output = DataObject(
            hash=joblib.hash(res, hash_name="sha1"), hash_method="joblib_SHA1",
            type="builtins.list", id=id(res), details={}, value=None)

        expected_container_1 = DataObject(
            hash=joblib.hash(TEST_ARRAY + 7, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res[0]),
            details={'shape': (3,), 'dtype': np.int64}, value=None)

        expected_container_2 = DataObject(
            hash=joblib.hash(TEST_ARRAY + 8, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res[1]),
            details={'shape': (3,), 'dtype': np.int64}, value=None)

        # Check the subscript of each array with respect to the list returned
        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: expected_output},
            exp_params={'index': 0},
            exp_output={0: expected_container_1},
            exp_arg_map=None,
            exp_kwarg_map=None,
            exp_code_stmnt=None,
            exp_return_targets=[],
            exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[1],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: expected_output},
            exp_params={'index': 1},
            exp_output={0: expected_container_2},
            exp_arg_map=None,
            exp_kwarg_map=None,
            exp_code_stmnt=None,
            exp_return_targets=[],
            exp_order=None,
            test_case=self)

        # Main function execution
        _check_function_execution(
            actual=Provenance.history[2],
            exp_function=FunctionInfo('container_output_function_level_0',
                                      'test_decorator', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={'param1': 3, 'param2': 6},
            exp_output={0: expected_output},
            exp_arg_map=['array', 'param1', 'param2'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = container_output_function_level_0(TEST_ARRAY, 3, 6)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_container_output_function_level_1(self):
        activate(clear=True)
        res = container_output_function_level_1(TEST_ARRAY, 4, 6)
        deactivate()

        self.assertEqual(len(Provenance.history), 9)

        elements = [[], []]
        for idx, container in enumerate(res):
            for element in container:
                element_info = DataObject(
                    hash=joblib.hash(element, hash_name="sha1"),
                    hash_method="joblib_SHA1",
                    type="numpy.int64", id=None,
                    details={'shape': (), 'dtype': np.int64},
                    value=element)
                elements[idx].append(element_info)

        expected_output = DataObject(
            hash=joblib.hash(res, hash_name="sha1"), hash_method="joblib_SHA1",
            type="builtins.list", id=id(res), details={}, value=None)

        expected_container_1 = DataObject(
            hash=joblib.hash(TEST_ARRAY + 2, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res[0]),
            details={'shape': (3,), 'dtype': np.int64}, value=None)

        expected_container_2 = DataObject(
            hash=joblib.hash(TEST_ARRAY + 3, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res[1]),
            details={'shape': (3,), 'dtype': np.int64}, value=None)

        # Check subscript of each element with respect to the array
        containers = [expected_container_1, expected_container_2]
        for history_index, element_index in zip(
                (1, 2, 3, 5, 6, 7),
                ((0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2))):
            container = element_index[0]
            element = element_index[1]
            _check_function_execution(
                actual=Provenance.history[history_index],
                exp_function=FunctionInfo('subscript', '', ''),
                exp_input={0: containers[container]},
                exp_params={'index': element},
                exp_output={0: elements[container][element]},
                exp_arg_map=None,
                exp_kwarg_map=None,
                exp_code_stmnt=None,
                exp_return_targets=[],
                exp_order=None,
                test_case=self)

        # Check the subscript of each array with respect to the list returned
        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: expected_output},
            exp_params={'index': 0},
            exp_output={0: expected_container_1},
            exp_arg_map=None,
            exp_kwarg_map=None,
            exp_code_stmnt=None,
            exp_return_targets=[],
            exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[4],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: expected_output},
            exp_params={'index': 1},
            exp_output={0: expected_container_2},
            exp_arg_map=None,
            exp_kwarg_map=None,
            exp_code_stmnt=None,
            exp_return_targets=[],
            exp_order=None,
            test_case=self)

        # Main function execution
        _check_function_execution(
            actual=Provenance.history[8],
            exp_function=FunctionInfo('container_output_function_level_1',
                                      'test_decorator', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={'param1': 4, 'param2': 6},
            exp_output={0: expected_output},
            exp_arg_map=['array', 'param1', 'param2'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = container_output_function_level_1(TEST_ARRAY, 4, 6)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_container_output_function_level_range_0_0(self):
        # Should be similar to `container_output=0`
        activate(clear=True)
        res = container_output_function_level_range_0_0(TEST_ARRAY, 3, 6)
        deactivate()

        self.assertEqual(len(Provenance.history), 3)

        expected_output = DataObject(
            hash=joblib.hash(res, hash_name="sha1"), hash_method="joblib_SHA1",
            type="builtins.list", id=id(res), details={}, value=None)

        expected_container_1 = DataObject(
            hash=joblib.hash(TEST_ARRAY + 1, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res[0]),
            details={'shape': (3,), 'dtype': np.int64}, value=None)

        expected_container_2 = DataObject(
            hash=joblib.hash(TEST_ARRAY + 2, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res[1]),
            details={'shape': (3,), 'dtype': np.int64}, value=None)

        # Check the subscript of each array with respect to the list returned
        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: expected_output},
            exp_params={'index': 0},
            exp_output={0: expected_container_1},
            exp_arg_map=None,
            exp_kwarg_map=None,
            exp_code_stmnt=None,
            exp_return_targets=[],
            exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[1],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: expected_output},
            exp_params={'index': 1},
            exp_output={0: expected_container_2},
            exp_arg_map=None,
            exp_kwarg_map=None,
            exp_code_stmnt=None,
            exp_return_targets=[],
            exp_order=None,
            test_case=self)

        # Main function execution
        _check_function_execution(
            actual=Provenance.history[2],
            exp_function=FunctionInfo('container_output_function_level_range_0_0',
                                      'test_decorator', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={'param1': 3, 'param2': 6},
            exp_output={0: expected_output},
            exp_arg_map=['array', 'param1', 'param2'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = container_output_function_level_range_0_0(TEST_ARRAY, 3, 6)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_container_output_function_level_range_0_1(self):
        # Should be similar to `container_output=1`
        activate(clear=True)
        res = container_output_function_level_range_0_1(TEST_ARRAY, 4, 6)
        deactivate()

        self.assertEqual(len(Provenance.history), 9)

        elements = [[], []]
        for idx, container in enumerate(res):
            for el_idx, element in enumerate(container):
                element_info = DataObject(
                    hash=joblib.hash(element, hash_name="sha1"),
                    hash_method="joblib_SHA1",
                    type="numpy.int64", id=None,
                    details={'shape': (), 'dtype': np.int64}, value=element)
                elements[idx].append(element_info)

        expected_output = DataObject(
            hash=joblib.hash(res, hash_name="sha1"), hash_method="joblib_SHA1",
            type="builtins.list", id=id(res), details={}, value=None)

        expected_container_1 = DataObject(
            hash=joblib.hash(TEST_ARRAY + 5, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res[0]),
            details={'shape': (3,), 'dtype': np.int64}, value=None)

        expected_container_2 = DataObject(
            hash=joblib.hash(TEST_ARRAY + 6, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res[1]),
            details={'shape': (3,), 'dtype': np.int64}, value=None)

        # Check subscript of each element with respect to the array
        containers = [expected_container_1, expected_container_2]
        for history_index, element_index in zip(
                (1, 2, 3, 5, 6, 7),
                ((0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2))):
            container = element_index[0]
            element = element_index[1]
            _check_function_execution(
                actual=Provenance.history[history_index],
                exp_function=FunctionInfo('subscript', '', ''),
                exp_input={0: containers[container]},
                exp_params={'index': element},
                exp_output={0: elements[container][element]},
                exp_arg_map=None,
                exp_kwarg_map=None,
                exp_code_stmnt=None,
                exp_return_targets=[],
                exp_order=None,
                test_case=self)

        # Check the subscript of each array with respect to the list returned
        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: expected_output},
            exp_params={'index': 0},
            exp_output={0: expected_container_1},
            exp_arg_map=None,
            exp_kwarg_map=None,
            exp_code_stmnt=None,
            exp_return_targets=[],
            exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[4],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: expected_output},
            exp_params={'index': 1},
            exp_output={0: expected_container_2},
            exp_arg_map=None,
            exp_kwarg_map=None,
            exp_code_stmnt=None,
            exp_return_targets=[],
            exp_order=None,
            test_case=self)

        # Main function execution
        _check_function_execution(
            actual=Provenance.history[8],
            exp_function=FunctionInfo('container_output_function_level_range_0_1',
                                      'test_decorator', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={'param1': 4, 'param2': 6},
            exp_output={0: expected_output},
            exp_arg_map=['array', 'param1', 'param2'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = container_output_function_level_range_0_1(TEST_ARRAY, 4, 6)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_container_output_function_level_range_1_1(self):
        activate(clear=True)
        res = container_output_function_level_range_1_1(TEST_ARRAY, 4, 6)
        deactivate()

        self.assertEqual(len(Provenance.history), 7)

        elements = [[], []]
        for idx, container in enumerate(res):
            for el_idx, element in enumerate(container):
                element_info = DataObject(
                    hash=joblib.hash(element, hash_name="sha1"),
                    hash_method="joblib_SHA1",
                    type="numpy.int64", id=None,
                    details={'shape': (), 'dtype': np.int64},
                    value=element)
                elements[idx].append(element_info)

        expected_container_1 = DataObject(
            hash=joblib.hash(TEST_ARRAY + 4, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res[0]),
            details={'shape': (3,), 'dtype': np.int64},
            value=None)

        expected_container_2 = DataObject(
            hash=joblib.hash(TEST_ARRAY + 5, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res[1]),
            details={'shape': (3,), 'dtype': np.int64},
            value=None)

        # Check subscript of each element with respect to the array
        containers = [expected_container_1, expected_container_2]
        for history_index, element_index in zip(
                (0, 1, 2, 3, 4, 5),
                ((0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2))):
            container = element_index[0]
            element = element_index[1]
            _check_function_execution(
                actual=Provenance.history[history_index],
                exp_function=FunctionInfo('subscript', '', ''),
                exp_input={0: containers[container]},
                exp_params={'index': element},
                exp_output={0: elements[container][element]},
                exp_arg_map=None,
                exp_kwarg_map=None,
                exp_code_stmnt=None,
                exp_return_targets=[],
                exp_order=None,
                test_case=self)

        # Main function execution
        # There is no single list return directly from the function
        _check_function_execution(
            actual=Provenance.history[6],
            exp_function=FunctionInfo('container_output_function_level_range_1_1',
                                      'test_decorator', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={'param1': 4, 'param2': 6},
            exp_output={0: expected_container_1, 1: expected_container_2},
            exp_arg_map=['array', 'param1', 'param2'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = container_output_function_level_range_1_1(TEST_ARRAY, 4, 6)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_dict_output_function(self):
        activate(clear=True)
        res = dict_output_function(TEST_ARRAY, 3, 7)
        deactivate()

        self.assertEqual(len(Provenance.history), 3)

        expected_output = DataObject(
            hash=joblib.hash(res, hash_name="sha1"), hash_method="joblib_SHA1",
            type="builtins.dict", id=id(res), details={}, value=None)

        expected_container_1 = DataObject(
            hash=joblib.hash(TEST_ARRAY + 3, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res['key.0']),
            details={'shape': (3,), 'dtype': np.int64},
            value=None)

        expected_container_2 = DataObject(
            hash=joblib.hash(TEST_ARRAY + 4, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res['key.1']),
            details={'shape': (3,), 'dtype': np.int64},
            value=None)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: expected_output},
            exp_params={'index': 'key.0'},
            exp_output={0: expected_container_1},
            exp_arg_map=None,
            exp_kwarg_map=None,
            exp_code_stmnt=None,
            exp_return_targets=[],
            exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[1],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: expected_output},
            exp_params={'index': 'key.1'},
            exp_output={0: expected_container_2},
            exp_arg_map=None,
            exp_kwarg_map=None,
            exp_code_stmnt=None,
            exp_return_targets=[],
            exp_order=None,
            test_case=self)

        # Main function execution
        _check_function_execution(
            actual=Provenance.history[2],
            exp_function=FunctionInfo('dict_output_function',
                                      'test_decorator', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={'param1': 3, 'param2': 7},
            exp_output={0: expected_output},
            exp_arg_map=['array', 'param1', 'param2'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = dict_output_function(TEST_ARRAY, 3, 7)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_dict_output_function_level(self):
        activate(clear=True)
        res = dict_output_function_level(TEST_ARRAY, 3, 8)
        deactivate()

        self.assertEqual(len(Provenance.history), 9)

        elements = {'key.0': [], 'key.1': []}
        for key, container in res.items():
            for element in container:
                element_info = DataObject(
                    hash=joblib.hash(element, hash_name="sha1"),
                    hash_method="joblib_SHA1",
                    type="numpy.int64", id=None,
                    details={'shape': (), 'dtype': np.int64},
                    value=element)
                elements[key].append(element_info)

        expected_output = DataObject(
            hash=joblib.hash(res, hash_name="sha1"), hash_method="joblib_SHA1",
            type="builtins.dict", id=id(res), details={}, value=None)

        expected_container_1 = DataObject(
            hash=joblib.hash(TEST_ARRAY + 3, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res['key.0']),
            details={'shape': (3,), 'dtype': np.int64},
            value=None)

        expected_container_2 = DataObject(
            hash=joblib.hash(TEST_ARRAY + 4, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res['key.1']),
            details={'shape': (3,), 'dtype': np.int64},
            value=None)

        # Check subscript of each element with respect to the array
        containers = {
            'key.0': expected_container_1,
            'key.1': expected_container_2
        }
        for history_index, element_index in zip(
                (1, 2, 3, 5, 6, 7),
                (('key.0', 0), ('key.0', 1), ('key.0', 2),
                 ('key.1', 0), ('key.1', 1), ('key.1', 2))):
            container = element_index[0]
            element = element_index[1]
            _check_function_execution(
                actual=Provenance.history[history_index],
                exp_function=FunctionInfo('subscript', '', ''),
                exp_input={0: containers[container]},
                exp_params={'index': element},
                exp_output={0: elements[container][element]},
                exp_arg_map=None,
                exp_kwarg_map=None,
                exp_code_stmnt=None,
                exp_return_targets=[],
                exp_order=None,
                test_case=self)

        # Check subscript of each array with respect to the dictionary returned
        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: expected_output},
            exp_params={'index': 'key.0'},
            exp_output={0: expected_container_1},
            exp_arg_map=None,
            exp_kwarg_map=None,
            exp_code_stmnt=None,
            exp_return_targets=[],
            exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[4],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: expected_output},
            exp_params={'index': 'key.1'},
            exp_output={0: expected_container_2},
            exp_arg_map=None,
            exp_kwarg_map=None,
            exp_code_stmnt=None,
            exp_return_targets=[],
            exp_order=None,
            test_case=self)

        # Main function execution
        _check_function_execution(
            actual=Provenance.history[8],
            exp_function=FunctionInfo('dict_output_function_level',
                                      'test_decorator', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={'param1': 3, 'param2': 8},
            exp_output={0: expected_output},
            exp_arg_map=['array', 'param1', 'param2'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = dict_output_function_level(TEST_ARRAY, 3, 8)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_non_iterable_container_output(self):
        activate(clear=True)
        res = non_iterable_container_output(3)
        deactivate()

        self.assertEqual(len(Provenance.history), 4)

        elements = []
        for element in res:
            element_info = DataObject(
                hash=joblib.hash(element, hash_name="sha1"),
                hash_method="joblib_SHA1",
                type="numpy.int64", id=None,
                details={'shape': (), 'dtype': np.int64},
                value=element)
            elements.append(element_info)

        expected_output = DataObject(
            hash=joblib.hash(res, hash_name="sha1"), hash_method="joblib_SHA1",
            type="test_decorator.NonIterableContainer", id=id(res),
            details={'data': res.data}, value=None)

        # Check subscript of each element with respect to the container
        for history_index in (0, 1, 2):
            element = elements[history_index]
            _check_function_execution(
                actual=Provenance.history[history_index],
                exp_function=FunctionInfo('subscript', '', ''),
                exp_input={0: expected_output},
                exp_params={'index': history_index},
                exp_output={0: element},
                exp_arg_map=None,
                exp_kwarg_map=None,
                exp_code_stmnt=None,
                exp_return_targets=[],
                exp_order=None,
                test_case=self)

        # Main function execution
        _check_function_execution(
            actual=Provenance.history[3],
            exp_function=FunctionInfo('non_iterable_container_output',
                                      'test_decorator', ''),
            exp_input={},
            exp_params={'param1': 3},
            exp_output={0: expected_output},
            exp_arg_map=['param1'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = non_iterable_container_output(3)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_comprehensions(self):
        activate(clear=True)
        num_list = [comprehension_function(i) for i in range(3)]
        num_set = {comprehension_function(i) for i in range(3, 6)}
        num_dict = {i: comprehension_function(v) for i, v in enumerate(range(6, 9), start=1)}
        deactivate()

        self.assertEqual(len(Provenance.history), 9)
        self.assertEqual(len(num_list), 3)
        self.assertEqual(len(num_set), 3)
        self.assertEqual(list(num_dict.keys()), [1, 2, 3])

        # Check executions of the list comprehension
        for history, element in zip((0, 1, 2), num_list):
            expected_output = DataObject(
                hash=joblib.hash(element, hash_name='sha1'),
                hash_method="joblib_SHA1",
                type="numpy.float64", id=id(element),
                details={'shape': (), 'dtype': np.float64},
                value=element)

            _check_function_execution(
                actual=Provenance.history[history],
                exp_function=FunctionInfo('comprehension_function',
                                          'test_decorator', ''),
                exp_input={},
                exp_params={'param': history},
                exp_output={0: expected_output},
                exp_arg_map=['param'],
                exp_kwarg_map=[],
                exp_code_stmnt="num_list = [comprehension_function(i) for i in range(3)]",
                exp_return_targets=['num_list'],
                exp_order=1+history,
                test_case=self)

        # Check executions of the set comprehension
        for history, element in zip((3, 4, 5), num_set):
            expected_output = DataObject(
                hash=joblib.hash(element, hash_name='sha1'),
                hash_method="joblib_SHA1",
                type="numpy.float64", id=id(element),
                details={'shape': (), 'dtype': np.float64},
                value=element)

            _check_function_execution(
                actual=Provenance.history[history],
                exp_function=FunctionInfo('comprehension_function',
                                          'test_decorator', ''),
                exp_input={},
                exp_params={'param': history},
                exp_output={0: expected_output},
                exp_arg_map=['param'],
                exp_kwarg_map=[],
                exp_code_stmnt="num_set = {comprehension_function(i) for i in range(3, 6)}",
                exp_return_targets=['num_set'],
                exp_order=1+history,
                test_case=self)

        # Check executions of the dict comprehension
        for history, element in zip((6, 7, 8), num_dict.values()):
            expected_output = DataObject(
                hash=joblib.hash(element, hash_name='sha1'),
                hash_method="joblib_SHA1",
                type="numpy.float64", id=id(element),
                details={'shape': (), 'dtype': np.float64},
                value=element)

            _check_function_execution(
                actual=Provenance.history[history],
                exp_function=FunctionInfo('comprehension_function',
                                          'test_decorator', ''),
                exp_input={},
                exp_params={'param': history},
                exp_output={0: expected_output},
                exp_arg_map=['param'],
                exp_kwarg_map=[],
                exp_code_stmnt="num_dict = {i: comprehension_function(v) for i, v in enumerate(range(6, 9), start=1)}",
                exp_return_targets=['num_dict'],
                exp_order=1+history,
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
            type="builtins.list", id=id(res), details={}, value=None)

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
            type="builtins.list", id=id(input_list), details={}, value=None)

        # As None has its own UUID, let's get what was generated
        self.assertEqual(len(Provenance.history), 1)
        output_uuid = Provenance.history[0].output[0].hash

        expected_none_output = DataObject(hash=output_uuid, hash_method="UUID",
            type="builtins.NoneType", id=id(res), details={}, value=None)

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

    @staticmethod
    def static_method(array, coefficient):
        return array + coefficient


ObjectWithMethod.process = Provenance(inputs=['self', 'array'])(
    ObjectWithMethod.process)

ObjectWithMethod.static_method = Provenance(inputs=['array'])(
    ObjectWithMethod.static_method)

# Apply decorator to method that uses the descriptor protocol
neo.AnalogSignal.reshape = Provenance(inputs=[0])(neo.AnalogSignal.reshape)


ObjectWithMethod.__init__ = Provenance(inputs=[])(ObjectWithMethod.__init__)


class ProvenanceDecoratorClassMethodsTestCase(unittest.TestCase):

    def test_static_method(self):
        obj = ObjectWithMethod(2)
        activate(clear=True)
        res = obj.static_method(TEST_ARRAY, 4)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)

        obj_info = DataObject(
            hash=joblib.hash(obj, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="test_decorator.ObjectWithMethod",
            id=id(obj),
            details={'coefficient': 2},
            value=None)

        expected_output = DataObject(
            hash=joblib.hash(TEST_ARRAY+4, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res),
            details={'shape': (3,), 'dtype': np.int64},
            value=None)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('ObjectWithMethod.static_method',
                                      'test_decorator', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={'coefficient': 4},
            exp_output={0: expected_output},
            exp_arg_map=['array', 'coefficient'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = obj.static_method(TEST_ARRAY, 4)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_method_descriptor(self):
        activate(clear=True)
        ansig = neo.AnalogSignal(TEST_ARRAY, units='mV', sampling_rate=1*pq.Hz)
        reshaped = ansig.reshape((1, -1))
        deactivate()

        self.assertEqual(len(Provenance.history), 1)

        expected_input = DataObject(
            hash=joblib.hash(ansig, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="neo.core.analogsignal.AnalogSignal", id=id(ansig),
            details={'_dimensionality': pq.mV.dimensionality,
                     '_t_start': 0 * pq.s, '_sampling_rate': 1 * pq.Hz,
                     'annotations': {}, 'array_annotations': {}, 'name': None,
                     'file_origin': None, 'description': None, 'segment': None,
                     'units': pq.mV.units, 'shape': (3, 1), 'dtype': np.int64,
                     't_start': 0 * pq.s, 't_stop': 3 * pq.s,
                     'dimensionality': pq.mV.dimensionality},
            value=None)

        expected_output = DataObject(
            hash=joblib.hash(reshaped, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="neo.core.analogsignal.AnalogSignal", id=id(reshaped),
            details={'_dimensionality': pq.mV.dimensionality,
                     '_t_start': 0 * pq.s, '_sampling_rate': 1 * pq.Hz,
                     'annotations': {}, 'array_annotations': {}, 'name': None,
                     'file_origin': None, 'description': None, 'segment': None,
                     'units': pq.mV.units, 'shape': (1, 3), 'dtype': np.int64,
                     't_start': 0 * pq.s, 't_stop': 1 * pq.s,
                     'dimensionality': pq.mV.dimensionality},
            value=None)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('ndarray.reshape',
                                      'numpy', np.__version__),
            exp_input={0: expected_input},
            exp_params={1: (1, -1)},
            exp_output={0: expected_output},
            exp_arg_map=[0, 1],
            exp_kwarg_map=[],
            exp_code_stmnt="reshaped = ansig.reshape((1, -1))",
            exp_return_targets=['reshaped'],
            exp_order=1,
            test_case=self)

    def test_class_constructor(self):
        activate(clear=True)
        obj = ObjectWithMethod(2)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)

        expected_output = DataObject(
            hash=joblib.hash(obj, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="test_decorator.ObjectWithMethod",
            id=id(obj),
            details={'coefficient': 2},
            value=None)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('ObjectWithMethod.__init__',
                                      'test_decorator', ''),
            exp_input={},
            exp_params={'coefficient': 2},
            exp_output={0: expected_output},
            exp_arg_map=['self', 'coefficient'],
            exp_kwarg_map=[],
            exp_code_stmnt="obj = ObjectWithMethod(2)",
            exp_return_targets=['obj'],
            exp_order=1,
            test_case=self)

    def test_object_method(self):
        obj = ObjectWithMethod(2)
        activate(clear=True)
        res = obj.process(TEST_ARRAY, 4, 5)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)

        obj_info = DataObject(
            hash=joblib.hash(obj, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="test_decorator.ObjectWithMethod",
            id=id(obj),
            details={'coefficient': 2}, value=None)

        expected_output = DataObject(
            hash=joblib.hash(TEST_ARRAY+2, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(res),
            details={'shape': (3,), 'dtype': np.int64}, value=None)

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

    def test_class_constructor_container_output(self):
        activate(clear=True)
        obj = NonIterableContainerOutputObject(2)
        deactivate()

        self.assertEqual(len(Provenance.history), 4)

        elements = []
        for element in obj:
                element_info = DataObject(
                    hash=joblib.hash(element, hash_name="sha1"),
                    hash_method="joblib_SHA1",
                    type="numpy.int64", id=None,
                    details={'shape': (), 'dtype': np.int64},
                    value=element)
                elements.append(element_info)

        expected_output = DataObject(
            hash=joblib.hash(obj, hash_name='sha1'),
            hash_method="joblib_SHA1",
            type="test_decorator.NonIterableContainerOutputObject",
            id=id(obj),
            details={'_data': obj._data},
            value=None)

        # Check subscript of each element with respect to the container
        for history_index in (0, 1, 2):
            element = elements[history_index]
            _check_function_execution(
                actual=Provenance.history[history_index],
                exp_function=FunctionInfo('subscript', '', ''),
                exp_input={0: expected_output},
                exp_params={'index': history_index},
                exp_output={0: element},
                exp_arg_map=None,
                exp_kwarg_map=None,
                exp_code_stmnt=None,
                exp_return_targets=[],
                exp_order=None,
                test_case=self)

        _check_function_execution(
            actual=Provenance.history[3],
            exp_function=FunctionInfo(
                'NonIterableContainerOutputObject.__init__',
                                      'test_decorator', ''),
            exp_input={},
            exp_params={'start': 2},
            exp_output={0: expected_output},
            exp_arg_map=['self', 'start'],
            exp_kwarg_map=[],
            exp_code_stmnt="obj = NonIterableContainerOutputObject(2)",
            exp_return_targets=['obj'],
            exp_order=1,
            test_case=self)


@Provenance(inputs=['source'])
def use_dict(source):
    return 3


class ProvenanceDecoratorStoreValuesTestCase(unittest.TestCase):

    def setUp(self):
        alpaca_setting('store_values', [])

    def test_capture_dict(self):
        # This should have values for both the input dictionary and the
        # integer return
        alpaca_setting('store_values', ['builtins.dict'])
        activate(clear=True)
        test_dict = dict(id=[1, 2, 3], value={4, 5, 6})
        res = use_dict(test_dict)
        deactivate()

        dict_info = DataObject(hash=joblib.hash(test_dict, hash_name='sha1'),
                               hash_method="joblib_SHA1",
                               type="builtins.dict", id=id(test_dict),
                               details={},
                               value="{'id': [1, 2, 3], 'value': {4, 5, 6}}")

        expected_output = DataObject(hash=joblib.hash(3, hash_name='sha1'),
                                     hash_method="joblib_SHA1",
                                     type="builtins.int", id=id(res),
                                     details={}, value=3)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('use_dict', 'test_decorator', ''),
            exp_input={'source': dict_info},
            exp_params={},
            exp_output={0: expected_output},
            exp_arg_map=['source'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = use_dict(test_dict)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_capture_builtins_only(self):
        # This should have values only for the integer return
        activate(clear=True)
        test_dict = dict(id=[1, 2, 3], value={4, 5, 6})
        res = use_dict(test_dict)
        deactivate()

        dict_info = DataObject(hash=joblib.hash(test_dict, hash_name='sha1'),
                               hash_method="joblib_SHA1",
                               type="builtins.dict", id=id(test_dict),
                               details={}, value=None)

        expected_output = DataObject(hash=joblib.hash(3, hash_name='sha1'),
                                     hash_method="joblib_SHA1",
                                     type="builtins.int", id=id(res),
                                     details={}, value=3)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('use_dict', 'test_decorator', ''),
            exp_input={'source': dict_info},
            exp_params={},
            exp_output={0: expected_output},
            exp_arg_map=['source'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = use_dict(test_dict)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)


if __name__ == "__main__":
    unittest.main()
