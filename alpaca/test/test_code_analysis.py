"""
These unit tests are done using the decorator with proper syntactic calls,
i.e., using static relationships in the inputs of the functions.

The files in the `ast` and `static_relationship_tree` files in `code_analysis`
are covered by the tests in this file.
"""

import unittest

import joblib
import datetime
from functools import partial

import numpy as np

from alpaca import Provenance, activate, deactivate
from alpaca.alpaca_types import FunctionInfo, DataObject
from alpaca.ontology.annotation import _OntologyInformation


# Shortcut for SHA1 hashing using joblib
joblib_hash = partial(joblib.hash, hash_name='sha1')


# Define some data for testing

TEST_ARRAY = np.array([1, 2, 3])
TEST_ARRAY_INFO = DataObject(hash=joblib_hash(TEST_ARRAY),
                             hash_method="joblib_SHA1",
                             type="numpy.ndarray", id=id(TEST_ARRAY),
                             details={'shape': (3,), 'dtype': np.int64},
                             value=None)

ELEMENT_0_INFO = DataObject(hash=joblib_hash(TEST_ARRAY[0]),
                            hash_method="joblib_SHA1", type="numpy.int64",
                            id=id(TEST_ARRAY[0]),
                            details={'shape': (), 'dtype': np.int64},
                            value=1)

ELEMENT_1_INFO = DataObject(hash=joblib_hash(TEST_ARRAY[1]),
                            hash_method="joblib_SHA1", type="numpy.int64",
                            id=id(TEST_ARRAY[1]),
                            details={'shape': (), 'dtype': np.int64},
                            value=2)

ELEMENT_2_INFO = DataObject(hash=joblib_hash(TEST_ARRAY[2]),
                            hash_method="joblib_SHA1", type="numpy.int64",
                            id=id(TEST_ARRAY[2]),
                            details={'shape': (), 'dtype': np.int64},
                            value=3)

TEST_DICT = {'numbers': TEST_ARRAY}
TEST_DICT_INFO = DataObject(hash=joblib_hash(TEST_DICT),
                            hash_method="joblib_SHA1",
                            type="builtins.dict", id=id(TEST_DICT),
                            details={}, value=None)


# To test attributes
class ContainerOfArray:
    def __init__(self, array):
        self.array = array


# To test attribute calls
class ObjectWithMethod:
    def add_numbers(self, array):
        return np.sum(array)
ObjectWithMethod.add_numbers = Provenance(inputs=['self', 'array'])(ObjectWithMethod.add_numbers)

class CustomObject:
    def __init__(self, data):
        self.data = data
CustomObject.__init__ = Provenance(inputs=['data'])(CustomObject.__init__)

# Define some test functions to use different relationships

@Provenance(inputs=['num1', 'num2'])
def add_numbers(num1, num2):
    return num1 + num2


@Provenance(inputs=['array'])
def add_numbers_array(array):
    return np.sum(array)


@Provenance(inputs=['array'])
def get_number(array, index):
    return array[index]


# Function to help verifying FunctionExecution tuples
# For subscripting, the IDs usually change, so we need to ignore them
def _check_function_execution(actual, exp_function, exp_input, exp_params,
                              exp_output, exp_arg_map, exp_kwarg_map,
                              exp_code_stmnt, exp_return_targets, exp_order,
                              test_case):

    data_object_attributes = ('hash', 'hash_method', 'type', 'details',
                              'value')

    # Check function
    test_case.assertTupleEqual(actual.function, exp_function)

    # Check inputs
    for input_arg, value in actual.input.items():
        test_case.assertTrue(input_arg in exp_input)
        for attr in data_object_attributes:
            test_case.assertEqual(getattr(value, attr),
                                  getattr(exp_input[input_arg], attr))

    # Check parameters
    test_case.assertDictEqual(actual.params, exp_params)

    # Check outputs
    for output, value in actual.output.items():
        test_case.assertTrue(output in exp_output)
        for attr in data_object_attributes:
            test_case.assertEqual(getattr(value, attr),
                                  getattr(exp_output[output], attr))

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


class ProvenanceDecoratorStaticRelationshipsTestCase(unittest.TestCase):

    def test_subscript_index(self):
        activate(clear=True)
        source_array = TEST_ARRAY
        res = add_numbers(source_array[0], source_array[1])
        deactivate()

        self.assertEqual(len(Provenance.history), 3)

        expected_output = DataObject(
            hash=joblib_hash(TEST_ARRAY[0]+TEST_ARRAY[1]),
            hash_method="joblib_SHA1",
            type="numpy.int64", id=id(res),
            details={'shape': (), 'dtype': np.int64}, value=3)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: TEST_ARRAY_INFO},
            exp_params={'index': 0},
            exp_output={0: ELEMENT_0_INFO},
            exp_arg_map=None, exp_kwarg_map=None, exp_code_stmnt=None,
            exp_return_targets=[], exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[1],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: TEST_ARRAY_INFO},
            exp_params={'index': 1},
            exp_output={0: ELEMENT_1_INFO},
            exp_arg_map=None, exp_kwarg_map=None, exp_code_stmnt=None,
            exp_return_targets=[], exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[2],
            exp_function=FunctionInfo('add_numbers',
                                      'test_code_analysis', ''),
            exp_input={'num1': ELEMENT_0_INFO, 'num2': ELEMENT_1_INFO},
            exp_params={},
            exp_output={0: expected_output},
            exp_arg_map=['num1', 'num2'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = add_numbers(source_array[0], source_array[1])",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_subscript_negative_index(self):
        activate(clear=True)
        source_array = TEST_ARRAY
        res = add_numbers(source_array[-1], source_array[-2])
        deactivate()

        self.assertEqual(len(Provenance.history), 3)

        expected_output = DataObject(
            hash=joblib_hash(TEST_ARRAY[-1]+TEST_ARRAY[-2]),
            hash_method="joblib_SHA1",
            type="numpy.int64", id=id(res),
            details={'shape': (), 'dtype': np.int64}, value=5)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: TEST_ARRAY_INFO},
            exp_params={'index': -1},
            exp_output={0: ELEMENT_2_INFO},
            exp_arg_map=None, exp_kwarg_map=None, exp_code_stmnt=None,
            exp_return_targets=[], exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[1],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: TEST_ARRAY_INFO},
            exp_params={'index': -2},
            exp_output={0: ELEMENT_1_INFO},
            exp_arg_map=None, exp_kwarg_map=None, exp_code_stmnt=None,
            exp_return_targets=[], exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[2],
            exp_function=FunctionInfo('add_numbers',
                                      'test_code_analysis', ''),
            exp_input={'num1': ELEMENT_2_INFO, 'num2': ELEMENT_1_INFO},
            exp_params={},
            exp_output={0: expected_output},
            exp_arg_map=['num1', 'num2'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = add_numbers(source_array[-1], source_array[-2])",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_subscript_slice(self):
        activate(clear=True)
        source_array = TEST_ARRAY
        res = add_numbers_array(source_array[0:2])
        deactivate()

        self.assertEqual(len(Provenance.history), 2)

        expected_output = DataObject(
            hash=joblib_hash(TEST_ARRAY[0]+TEST_ARRAY[1]),
            hash_method="joblib_SHA1",
            type="numpy.int64", id=id(res),
            details={'shape': (), 'dtype': np.int64}, value=3)

        expected_slice_output = DataObject(
            hash=joblib_hash(TEST_ARRAY[0:2]), hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(TEST_ARRAY[0:2]),
            details={'shape': (2,), 'dtype': np.int64}, value=None)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: TEST_ARRAY_INFO},
            exp_params={'slice': '0:2'},
            exp_output={0: expected_slice_output},
            exp_arg_map=None, exp_kwarg_map=None, exp_code_stmnt=None,
            exp_return_targets=[], exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[1],
            exp_function=FunctionInfo('add_numbers_array',
                                      'test_code_analysis', ''),
            exp_input={'array': expected_slice_output},
            exp_params={},
            exp_output={0: expected_output},
            exp_arg_map=['array'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = add_numbers_array(source_array[0:2])",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_subscript_slice_no_start(self):
        activate(clear=True)
        source_array = TEST_ARRAY
        res = add_numbers_array(source_array[:2])
        deactivate()

        self.assertEqual(len(Provenance.history), 2)

        expected_output = DataObject(
            hash=joblib_hash(TEST_ARRAY[0]+TEST_ARRAY[1]),
            hash_method="joblib_SHA1",
            type="numpy.int64", id=id(res),
            details={'shape': (), 'dtype': np.int64}, value=3)

        expected_slice_output = DataObject(
            hash=joblib_hash(TEST_ARRAY[:2]), hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(TEST_ARRAY[:2]),
            details={'shape': (2,), 'dtype': np.int64}, value=None)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: TEST_ARRAY_INFO},
            exp_params={'slice': ':2'},
            exp_output={0: expected_slice_output},
            exp_arg_map=None, exp_kwarg_map=None, exp_code_stmnt=None,
            exp_return_targets=[], exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[1],
            exp_function=FunctionInfo('add_numbers_array',
                                      'test_code_analysis', ''),
            exp_input={'array': expected_slice_output},
            exp_params={},
            exp_output={0: expected_output},
            exp_arg_map=['array'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = add_numbers_array(source_array[:2])",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_subscript_slice_no_stop(self):
        activate(clear=True)
        source_array = TEST_ARRAY
        res = add_numbers_array(source_array[1:])
        deactivate()

        self.assertEqual(len(Provenance.history), 2)

        expected_output = DataObject(
            hash=joblib_hash(TEST_ARRAY[1]+TEST_ARRAY[2]),
            hash_method="joblib_SHA1",
            type="numpy.int64", id=id(res),
            details={'shape': (), 'dtype': np.int64}, value=5)

        expected_slice_output = DataObject(
            hash=joblib_hash(TEST_ARRAY[1:]), hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(TEST_ARRAY[1:]),
            details={'shape': (2,), 'dtype': np.int64}, value=None)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: TEST_ARRAY_INFO},
            exp_params={'slice': '1:'},
            exp_output={0: expected_slice_output},
            exp_arg_map=None, exp_kwarg_map=None, exp_code_stmnt=None,
            exp_return_targets=[], exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[1],
            exp_function=FunctionInfo('add_numbers_array',
                                      'test_code_analysis', ''),
            exp_input={'array': expected_slice_output},
            exp_params={},
            exp_output={0: expected_output},
            exp_arg_map=['array'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = add_numbers_array(source_array[1:])",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_subscript_slice_step(self):
        activate(clear=True)
        source_array = TEST_ARRAY
        res = add_numbers_array(source_array[::2])
        deactivate()

        self.assertEqual(len(Provenance.history), 2)

        expected_output = DataObject(
            hash=joblib_hash(TEST_ARRAY[0]+TEST_ARRAY[2]),
            hash_method="joblib_SHA1",
            type="numpy.int64", id=id(res),
            details={'shape': (), 'dtype': np.int64}, value=4)

        expected_slice_output = DataObject(
            hash=joblib_hash(TEST_ARRAY[::2]), hash_method="joblib_SHA1",
            type="numpy.ndarray", id=id(TEST_ARRAY[::2]),
            details={'shape': (2,), 'dtype': np.int64}, value=None)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: TEST_ARRAY_INFO},
            exp_params={'slice': '::2'},
            exp_output={0: expected_slice_output},
            exp_arg_map=None, exp_kwarg_map=None, exp_code_stmnt=None,
            exp_return_targets=[], exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[1],
            exp_function=FunctionInfo('add_numbers_array',
                                      'test_code_analysis', ''),
            exp_input={'array': expected_slice_output},
            exp_params={},
            exp_output={0: expected_output},
            exp_arg_map=['array'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = add_numbers_array(source_array[::2])",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_subscript_index_str(self):
        activate(clear=True)
        source_dict = TEST_DICT
        res = add_numbers_array(source_dict['numbers'])
        deactivate()

        self.assertEqual(len(Provenance.history), 2)

        expected_output = DataObject(
            hash=joblib_hash(np.sum(TEST_ARRAY)),
            hash_method="joblib_SHA1",
            type="numpy.int64", id=id(res),
            details={'shape': (), 'dtype': np.int64}, value=6)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: TEST_DICT_INFO},
            exp_params={'index': 'numbers'},
            exp_output={0: TEST_ARRAY_INFO},
            exp_arg_map=None, exp_kwarg_map=None, exp_code_stmnt=None,
            exp_return_targets=[], exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[1],
            exp_function=FunctionInfo('add_numbers_array',
                                      'test_code_analysis', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={},
            exp_output={0: expected_output},
            exp_arg_map=['array'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = add_numbers_array(source_dict['numbers'])",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_subscript_index_from_variable(self):
        activate(clear=True)
        source_dict = TEST_DICT
        param_name = 'numbers'
        res = add_numbers_array(source_dict[param_name])
        deactivate()

        self.assertEqual(len(Provenance.history), 2)

        expected_output = DataObject(
            hash=joblib_hash(np.sum(TEST_ARRAY)),
            hash_method="joblib_SHA1",
            type="numpy.int64", id=id(res),
            details={'shape': (), 'dtype': np.int64}, value=6)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: TEST_DICT_INFO},
            exp_params={'index': 'numbers'},
            exp_output={0: TEST_ARRAY_INFO},
            exp_arg_map=None, exp_kwarg_map=None, exp_code_stmnt=None,
            exp_return_targets=[], exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[1],
            exp_function=FunctionInfo('add_numbers_array',
                                      'test_code_analysis', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={},
            exp_output={0: expected_output},
            exp_arg_map=['array'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = add_numbers_array(source_dict[param_name])",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_attribute(self):
        activate(clear=True)
        container_of_array = ContainerOfArray(TEST_ARRAY)
        res = add_numbers_array(container_of_array.array)
        deactivate()

        self.assertEqual(len(Provenance.history), 2)

        expected_output = DataObject(
            hash=joblib_hash(np.sum(TEST_ARRAY)),
            hash_method="joblib_SHA1",
            type="numpy.int64", id=id(res),
            details={'shape': (), 'dtype': np.int64}, value=6)

        expected_container_info = DataObject(
            hash=joblib_hash(container_of_array), hash_method="joblib_SHA1",
            type="test_code_analysis.ContainerOfArray",
            id=id(container_of_array), details={'array': TEST_ARRAY},
            value=None)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('attribute', '', ''),
            exp_input={0: expected_container_info},
            exp_params={'name': 'array'},
            exp_output={0: TEST_ARRAY_INFO},
            exp_arg_map=None, exp_kwarg_map=None, exp_code_stmnt=None,
            exp_return_targets=[], exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[1],
            exp_function=FunctionInfo('add_numbers_array',
                                      'test_code_analysis', ''),
            exp_input={'array': TEST_ARRAY_INFO},
            exp_params={},
            exp_output={0: expected_output},
            exp_arg_map=['array'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = add_numbers_array(container_of_array.array)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_attribute_method_call(self):
        activate(clear=True)
        object_with_method = ObjectWithMethod()
        container_of_array = ContainerOfArray(TEST_ARRAY)
        res = object_with_method.add_numbers(container_of_array.array)
        deactivate()

        self.assertEqual(len(Provenance.history), 2)

        expected_output = DataObject(
            hash=joblib_hash(np.sum(TEST_ARRAY)),
            hash_method="joblib_SHA1",
            type="numpy.int64", id=id(res),
            details={'shape': (), 'dtype': np.int64},
            value=6)

        object_info = DataObject(
            hash=joblib_hash(object_with_method),
            hash_method="joblib_SHA1",
            type="test_code_analysis.ObjectWithMethod",
            id=id(object_with_method),
            details={},
            value=None)

        expected_container_info = DataObject(
            hash=joblib_hash(container_of_array), hash_method="joblib_SHA1",
            type="test_code_analysis.ContainerOfArray",
            id=id(container_of_array), details={'array': TEST_ARRAY},
            value=None)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('attribute', '', ''),
            exp_input={0: expected_container_info},
            exp_params={'name': 'array'},
            exp_output={0: TEST_ARRAY_INFO},
            exp_arg_map=None, exp_kwarg_map=None, exp_code_stmnt=None,
            exp_return_targets=[], exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[1],
            exp_function=FunctionInfo('ObjectWithMethod.add_numbers',
                                      'test_code_analysis', ''),
            exp_input={'self': object_info, 'array': TEST_ARRAY_INFO},
            exp_params={},
            exp_output={0: expected_output},
            exp_arg_map=['self', 'array'],
            exp_kwarg_map=[],
            exp_code_stmnt="res = object_with_method.add_numbers(container_of_array.array)",
            exp_return_targets=['res'],
            exp_order=1,
            test_case=self)

    def test_subscript_initializer(self):
        activate(clear=True)
        list_1 = [1, 2, 3]
        list_2 = [3, 4, 5]
        source_data = [list_1, list_2]
        custom_object = CustomObject(source_data[0])
        deactivate()

        self.assertEqual(len(Provenance.history), 2)

        expected_output = DataObject(
            hash=joblib_hash(custom_object),
            hash_method="joblib_SHA1",
            type="test_code_analysis.CustomObject", id=id(custom_object),
            details={'data': list_1}, value=None)

        source_list_info = DataObject(
            hash=joblib_hash(source_data),
            hash_method="joblib_SHA1",
            type="builtins.list", id=id(source_data), details={},
            value=None)

        element_info = DataObject(
            hash=joblib_hash(list_1),
            hash_method="joblib_SHA1",
            type="builtins.list", id=id(list_1), details={},
            value=None)

        _check_function_execution(
            actual=Provenance.history[0],
            exp_function=FunctionInfo('subscript', '', ''),
            exp_input={0: source_list_info},
            exp_params={'index': 0},
            exp_output={0: element_info},
            exp_arg_map=None, exp_kwarg_map=None, exp_code_stmnt=None,
            exp_return_targets=[], exp_order=None,
            test_case=self)

        _check_function_execution(
            actual=Provenance.history[1],
            exp_function=FunctionInfo('CustomObject.__init__',
                                      'test_code_analysis', ''),
            exp_input={'data': element_info},
            exp_params={},
            exp_output={0: expected_output},
            exp_arg_map=['self', 'data'],
            exp_kwarg_map=[],
            exp_code_stmnt="custom_object = CustomObject(source_data[0])",
            exp_return_targets=['custom_object'],
            exp_order=1,
            test_case=self)


if __name__ == "__main__":
    unittest.main()
