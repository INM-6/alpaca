import unittest

import numpy as np

from alpaca.alpaca_types import File, DataObject
from alpaca.data_information import _FileInformation, _ObjectInformation

from pathlib import Path
import joblib
import uuid


class ObjectClass(object):
    """
    Class used to test hashing and getting data from custom objects
    """
    def __init__(self, param):
        self.param = param
        self.attribute = "an object class"


class FileInformationTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.file_path = Path(__file__).parent.absolute() / "res"

    def test_file_info_sha256(self):
        file_input = self.file_path / "file_input.txt"
        file_info = _FileInformation(file_input)
        info = file_info.info()
        self.assertIsInstance(info, File)
        self.assertEqual(info.hash_type, "sha256")
        self.assertEqual(info.hash, "96ccc1380e069667069acecea3e2ab559441657807e0a86d14f49028710ddb3a")
        self.assertEqual(info.path, file_input)

    def test_file_info_comparison(self):
        file_info_1 = _FileInformation(self.file_path / "file_input.txt")
        file_info_2 = _FileInformation(self.file_path / "file_input.txt")
        file_info_3 = _FileInformation(self.file_path / "file_output.txt")

        self.assertTrue(file_info_1 == file_info_2)

        with self.assertRaises(TypeError):
            comparison = file_info_1 == "other type"

        self.assertFalse(file_info_3 == file_info_1)

    def test_repr(self):
        file_info = _FileInformation(self.file_path / "file_input.txt")
        expected_str = "file_input.txt: [sha256] 96ccc1380e069667069acece" \
                       "a3e2ab559441657807e0a86d14f49028710ddb3a"
        self.assertEqual(str(file_info), expected_str)


class ObjectInformationTestCase(unittest.TestCase):

    def test_numpy_array(self):
        numpy_array_int = np.array([[1, 2, 3, 4],
                                    [5, 6, 7, 8],
                                    [9, 10, 11, 12]], dtype=np.int64)
        numpy_array_float = np.array([[1, 2, 3, 4],
                                      [5, 6, 7, 8],
                                      [9, 10, 11, 12]], dtype=np.float64)

        object_info = _ObjectInformation()
        info_int = object_info.info(numpy_array_int)
        info_float = object_info.info(numpy_array_float)

        self.assertIsInstance(info_int, DataObject)
        self.assertIsInstance(info_float, DataObject)

        self.assertEqual(info_int.type, "numpy.ndarray")
        self.assertEqual(info_float.type, "numpy.ndarray")
        self.assertEqual(info_int.details['shape'], (3, 4))
        self.assertEqual(info_float.details['shape'], (3, 4))
        self.assertEqual(info_int.details['dtype'], np.int64)
        self.assertEqual(info_float.details['dtype'], np.float64)
        self.assertEqual(info_int.id, id(numpy_array_int))
        self.assertEqual(info_float.id, id(numpy_array_float))
        self.assertEqual(info_int.hash_method, "joblib_SHA1")
        self.assertEqual(info_float.hash_method, "joblib_SHA1")
        self.assertEqual(info_int.hash, joblib.hash(numpy_array_int,
                                                    hash_name='sha1'))
        self.assertEqual(info_float.hash, joblib.hash(numpy_array_float,
                                                      hash_name='sha1'))

    def test_memoization(self):
        array = np.array([1, 2, 3])
        object_info = _ObjectInformation()
        array_id = id(array)

        self.assertDictEqual(object_info._hash_memoizer, {})
        self.assertFalse(array_id in object_info._hash_memoizer)
        info_pre = object_info.info(array)

        self.assertTrue(array_id in object_info._hash_memoizer)
        info_post = object_info.info(array)
        self.assertEqual(info_pre, info_post)

    def test_none(self):
        object_info = _ObjectInformation()
        info = object_info.info(None)
        self.assertIsInstance(info.hash, uuid.UUID)
        self.assertEqual(info.type, "builtins.NoneType")
        self.assertEqual(info.hash_method, "UUID")
        self.assertDictEqual(info.details, {})

    def test_store_value_requested(self):
        object_info = _ObjectInformation(store_values=['builtins.dict'])
        test_dict = dict(key=['3', '4'])
        info = object_info.info(test_dict)
        self.assertEqual(info.hash, joblib.hash(test_dict, hash_name='sha1'))
        self.assertEqual(info.type, "builtins.dict")
        self.assertEqual(info.hash_method, "joblib_SHA1")
        self.assertDictEqual(info.details, {})
        self.assertEqual(info.value, "{'key': ['3', '4']}")

    def test_store_value_not_requested(self):
        object_info = _ObjectInformation()
        test_dict = dict(key=['3', '4'])
        info = object_info.info(test_dict)
        self.assertEqual(info.hash, joblib.hash(test_dict, hash_name='sha1'))
        self.assertEqual(info.type, "builtins.dict")
        self.assertEqual(info.hash_method, "joblib_SHA1")
        self.assertDictEqual(info.details, {})
        self.assertEqual(info.value, None)

    def test_store_value_builtins(self):
        object_info = _ObjectInformation()
        info = object_info.info(5)
        self.assertEqual(info.hash, joblib.hash(5, hash_name='sha1'))
        self.assertEqual(info.type, "builtins.int")
        self.assertEqual(info.hash_method, "joblib_SHA1")
        self.assertDictEqual(info.details, {})
        self.assertEqual(info.value, 5)

    def test_custom_class(self):
        custom_object_1 = ObjectClass(param=4)
        custom_object_2 = ObjectClass(param=3)
        object_info = _ObjectInformation()

        info_1 = object_info.info(custom_object_1)
        self.assertEqual(info_1.details['param'], 4)
        self.assertEqual(info_1.details['attribute'], "an object class")
        self.assertEqual(info_1.id, id(custom_object_1))
        self.assertEqual(info_1.type, "test_data_information.ObjectClass")
        self.assertEqual(info_1.hash_method, "joblib_SHA1")
        self.assertEqual(info_1.hash, joblib.hash(custom_object_1,
                                                  hash_name='sha1'))

        info_2 = object_info.info(custom_object_2)
        self.assertEqual(info_2.details['param'], 3)
        self.assertEqual(info_2.details['attribute'], "an object class")
        self.assertEqual(info_2.id, id(custom_object_2))
        self.assertEqual(info_2.type, "test_data_information.ObjectClass")
        self.assertEqual(info_2.hash_method, "joblib_SHA1")
        self.assertEqual(info_2.hash, joblib.hash(custom_object_2,
                                                  hash_name='sha1'))

    def test_use_builtin_hash_simple(self):
        custom_object = ObjectClass(param=4)
        object_info = _ObjectInformation(
            use_builtin_hash=['test_data_information'])
        info = object_info.info(custom_object)
        self.assertEqual(info.details['param'], 4)
        self.assertEqual(info.details['attribute'], "an object class")
        self.assertEqual(info.id, id(custom_object))
        self.assertEqual(info.type, "test_data_information.ObjectClass")
        self.assertEqual(info.hash_method, "Python_hash")
        self.assertEqual(info.hash, hash(custom_object))

    def test_use_builtin_hash_container_list(self):
        custom_object_1 = ObjectClass(param=4)
        custom_object_2 = ObjectClass(param=3)
        object_info = _ObjectInformation(
            use_builtin_hash=['test_data_information'])

        container = [custom_object_1, custom_object_2]
        info = object_info.info(container)
        self.assertEqual(info.id, id(container))
        self.assertEqual(info.type, "builtins.list")
        self.assertEqual(info.hash_method, "Python_hash")

        expected_hashes = [hash(obj) for obj in container]

        self.assertEqual(info.hash, joblib.hash(tuple(expected_hashes),
                                                hash_name='sha1'))

    def test_use_builtin_hash_container_numpy_array(self):
        custom_object_1 = ObjectClass(param=4)
        custom_object_2 = ObjectClass(param=3)
        custom_object_3 = ObjectClass(param=7)
        custom_object_4 = ObjectClass(param=5)
        object_info = _ObjectInformation(
            use_builtin_hash=['test_data_information'])

        container = np.array([[custom_object_1, custom_object_2],
                              [custom_object_3, custom_object_4]])
        info = object_info.info(container)
        self.assertEqual(info.id, id(container))
        self.assertEqual(info.type, "numpy.ndarray")
        self.assertEqual(info.hash_method, "Python_hash")

        expected_hashes = []
        for row in container:
            for element in row:
                expected_hashes.append(hash(element))

        self.assertEqual(info.hash,
                         joblib.hash(tuple(expected_hashes), hash_name='sha1'))

    def test_use_builtin_hash_container_numpy_array_multiple_types(self):
        custom_object_1 = ObjectClass(param=4)
        custom_object_2 = ObjectClass(param=3)
        custom_object_3 = ObjectClass(param=7)
        object_info = _ObjectInformation(
            use_builtin_hash=['test_data_information'])

        container = np.array([[custom_object_1, custom_object_2],
                              [4, custom_object_3]])
        info = object_info.info(container)
        self.assertEqual(info.id, id(container))
        self.assertEqual(info.type, "numpy.ndarray")
        self.assertEqual(info.hash_method, "joblib_SHA1")

        self.assertEqual(info.hash, joblib.hash(container, hash_name='sha1'))


if __name__ == "__main__":
    unittest.main()
