import unittest

import numpy as np

from alpaca.object_hash import FileHash, FileInfo, ObjectHasher, ObjectInfo
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


class FileHashTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.file_path = Path(__file__).parent.absolute() / ("res/file_input.txt")

    def test_file_hash_sha256(self):
        file_hash = FileHash(self.file_path)
        info = file_hash.info()
        self.assertIsInstance(info, FileInfo)
        self.assertEqual(info.hash_type, "sha256")
        self.assertEqual(info.hash, "96ccc1380e069667069acecea3e2ab559441657807e0a86d14f49028710ddb3a")
        self.assertEqual(info.path, self.file_path)

    def test_file_hash_attribute(self):
        file_hash = FileHash(self.file_path, use_content=False)
        info = file_hash.info()
        self.assertIsInstance(info, FileInfo)
        self.assertEqual(info.hash_type, "attribute")
        self.assertEqual(info.hash, 0)
        self.assertEqual(info.path, self.file_path)

    def test_file_hash_comparison(self):
        file_hash_1 = FileHash(self.file_path)
        file_hash_2 = FileHash(self.file_path)
        file_hash_3 = FileHash(self.file_path, use_content=False)

        self.assertTrue(file_hash_1 == file_hash_2)

        with self.assertRaises(TypeError):
            comparison = file_hash_1 == "other type"

        self.assertFalse(file_hash_3 == file_hash_1)

    def test_repr(self):
        file_hash = FileHash(self.file_path)
        expected_str = "file_input.txt: [sha256] 96ccc1380e069667069acece" \
                       "a3e2ab559441657807e0a86d14f49028710ddb3a"
        self.assertEqual(str(file_hash), expected_str)


class ObjectHasherTestCase(unittest.TestCase):

    def test_numpy_array(self):
        numpy_array_int = np.array([[1, 2, 3, 4],
                                    [5, 6, 7, 8],
                                    [9, 10, 11, 12]], dtype=np.int64)
        numpy_array_float = np.array([[1, 2, 3, 4],
                                      [5, 6, 7, 8],
                                      [9, 10, 11, 12]], dtype=np.float64)

        object_hasher = ObjectHasher()
        info_int = object_hasher.info(numpy_array_int)
        info_float = object_hasher.info(numpy_array_float)

        self.assertIsInstance(info_int, ObjectInfo)
        self.assertIsInstance(info_float, ObjectInfo)

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
        object_hasher = ObjectHasher()
        array_id = id(array)

        self.assertDictEqual(object_hasher._hash_memoizer, {})
        self.assertFalse(array_id in object_hasher._hash_memoizer)
        info_pre = object_hasher.info(array)

        self.assertTrue(array_id in object_hasher._hash_memoizer)
        info_post = object_hasher.info(array)
        self.assertEqual(info_pre, info_post)

    def test_none(self):
        object_hasher = ObjectHasher()
        info = object_hasher.info(None)
        self.assertIsInstance(info.hash, uuid.UUID)
        self.assertEqual(info.type, "builtins.NoneType")
        self.assertDictEqual(info.details, {})

    def test_custom_class(self):
        custom_object_1 = ObjectClass(param=4)
        custom_object_2 = ObjectClass(param=3)
        object_hasher = ObjectHasher()

        info_1 = object_hasher.info(custom_object_1)
        self.assertEqual(info_1.details['param'], 4)
        self.assertEqual(info_1.details['attribute'], "an object class")
        self.assertEqual(info_1.id, id(custom_object_1))
        self.assertEqual(info_1.type, "test_object_hash.ObjectClass")
        self.assertEqual(info_1.hash, joblib.hash(custom_object_1,
                                                  hash_name='sha1'))

        info_2 = object_hasher.info(custom_object_2)
        self.assertEqual(info_2.details['param'], 3)
        self.assertEqual(info_2.details['attribute'], "an object class")
        self.assertEqual(info_2.id, id(custom_object_2))
        self.assertEqual(info_2.type, "test_object_hash.ObjectClass")
        self.assertEqual(info_2.hash, joblib.hash(custom_object_2,
                                                  hash_name='sha1'))


if __name__ == "__main__":
    unittest.main()
