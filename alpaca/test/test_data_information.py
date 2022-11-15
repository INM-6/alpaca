import unittest

import numpy as np

from alpaca.types import File, DataObject
from alpaca.data_information import (_FileInformation, _ObjectInformation)
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
        cls.file_path = Path(__file__).parent.absolute() / ("res/file_input.txt")

    def test_file_info_sha256(self):
        file_info = _FileInformation(self.file_path)
        info = file_info.info()
        self.assertIsInstance(info, File)
        self.assertEqual(info.hash_type, "sha256")
        self.assertEqual(info.hash, "96ccc1380e069667069acecea3e2ab559441657807e0a86d14f49028710ddb3a")
        self.assertEqual(info.path, self.file_path)

    def test_file_info_attribute(self):
        file_info = _FileInformation(self.file_path, use_content=False)
        info = file_info.info()
        self.assertIsInstance(info, File)
        self.assertEqual(info.hash_type, "attribute")
        self.assertEqual(info.hash, 0)
        self.assertEqual(info.path, self.file_path)

    def test_file_info_comparison(self):
        file_info_1 = _FileInformation(self.file_path)
        file_info_2 = _FileInformation(self.file_path)
        file_info_3 = _FileInformation(self.file_path, use_content=False)

        self.assertTrue(file_info_1 == file_info_2)

        with self.assertRaises(TypeError):
            comparison = file_info_1 == "other type"

        self.assertFalse(file_info_3 == file_info_1)

    def test_repr(self):
        file_info = _FileInformation(self.file_path)
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
        self.assertDictEqual(info.details, {})

    def test_custom_class(self):
        custom_object_1 = ObjectClass(param=4)
        custom_object_2 = ObjectClass(param=3)
        object_info = _ObjectInformation()

        info_1 = object_info.info(custom_object_1)
        self.assertEqual(info_1.details['param'], 4)
        self.assertEqual(info_1.details['attribute'], "an object class")
        self.assertEqual(info_1.id, id(custom_object_1))
        self.assertEqual(info_1.type, "test_data_information.ObjectClass")
        self.assertEqual(info_1.hash, joblib.hash(custom_object_1,
                                                  hash_name='sha1'))

        info_2 = object_info.info(custom_object_2)
        self.assertEqual(info_2.details['param'], 3)
        self.assertEqual(info_2.details['attribute'], "an object class")
        self.assertEqual(info_2.id, id(custom_object_2))
        self.assertEqual(info_2.type, "test_data_information.ObjectClass")
        self.assertEqual(info_2.hash, joblib.hash(custom_object_2,
                                                  hash_name='sha1'))


if __name__ == "__main__":
    unittest.main()
