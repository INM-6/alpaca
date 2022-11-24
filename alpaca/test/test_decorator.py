import unittest

import joblib
import datetime

import numpy as np

from alpaca import (Provenance, activate, deactivate, save_provenance,
                    print_history)
from alpaca.alpaca_types import (FunctionInfo, Container, DataObject, File)

# Define some data and expected values test tracking

TEST_ARRAY = np.array([1, 2, 3])
TEST_ARRAY_INFO = DataObject(hash=joblib.hash(TEST_ARRAY, hash_name='sha1'),
                             hash_method="joblib",
                             type="numpy.ndarray", id=id(TEST_ARRAY),
                             details={'shape': (3,), 'dtype': np.int64})

TEST_ARRAY_2 = np.array([4, 5, 6])
TEST_ARRAY_2_INFO = DataObject(hash=joblib.hash(TEST_ARRAY_2,
                                                hash_name='sha1'),
                               hash_method="joblib",
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


class ProvenanceDecoratorInputOutputCombinationsTestCase(unittest.TestCase):

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

    def test_simple_function(self):
        activate(clear=True)
        res = simple_function(TEST_ARRAY, 1, 2)
        deactivate()

        self.assertEqual(len(Provenance.history), 1)

        expected_output = DataObject(
            hash=joblib.hash(TEST_ARRAY+3, hash_name='sha1'),
            hash_method="joblib",
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
            hash_method="joblib",
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
            hash_method="joblib",
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
            hash_method="joblib",
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
            hash_method="joblib",
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
            hash_method="joblib",
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
            hash_method="joblib",
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


if __name__ == "__main__":
    unittest.main()
