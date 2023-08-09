import unittest

from alpaca.utils.files import _get_prov_file_format, _get_file_format
from alpaca.utils import get_file_name
from os.path import expanduser


USER_PATH = expanduser("~")


class FileUtilsTestCase(unittest.TestCase):

    def test_get_file_name_user_path_new_extension(self):
        source_path = "~/test.py"
        new_path = get_file_name(source_path, None, "ttl")
        self.assertEqual(new_path, USER_PATH + "/test.ttl")

    def test_get_file_name_file_suffix_new_extension(self):
        source_path = "~/test.py"
        new_path = get_file_name(source_path, None, "ttl",
                                 suffix="_5")
        self.assertEqual(new_path, USER_PATH + "/test_5.ttl")

    def test_get_file_name_file_suffix(self):
        source_path = "~/test.py"
        new_path = get_file_name(source_path, None, None,
                                 suffix="_5")
        self.assertEqual(new_path, USER_PATH + "/test_5.py")

    def test_get_file_name_user_path_new_extension2(self):
        source_path = "~/test.py"
        new_path = get_file_name(source_path, None, ".ttl")
        self.assertEqual(new_path, USER_PATH + "/test.ttl")

    def test_get_file_name_abs_path_new_extension(self):
        source_path = "/home/user/test.py"
        new_path = get_file_name(source_path, None, "ttl")
        self.assertEqual(new_path, "/home/user/test.ttl")

    def test_get_file_name_abs_path_new_extension2(self):
        source_path = "/home/user/test.py"
        new_path = get_file_name(source_path, None, ".ttl")
        self.assertEqual(new_path, "/home/user/test.ttl")

    def test_get_file_name_new_path_same_extension(self):
        source_path = "/home/user/test.py"
        new_path = get_file_name(source_path, "/user_result", None)
        self.assertEqual(new_path, "/user_result/test.py")

    def test_get_file_name_new_path_new_extension(self):
        source_path = "/home/user/test.py"
        new_path = get_file_name(source_path, "/user_result", ".rdf")
        self.assertEqual(new_path, "/user_result/test.rdf")

    def test_get_file_name_relative_path(self):
        source_path = "/home/../user/test.py"
        new_path = get_file_name(source_path, None, ".rdf")
        self.assertEqual(new_path, "/user/test.rdf")

    def test_get_file_name_new_relative_path(self):
        source_path = "/home/user/test.py"
        new_path = get_file_name(source_path, "/test/../", None)
        self.assertEqual(new_path, "/test.py")

    def test_get_file_name_no_change_user(self):
        source_path = "~/test.py"
        new_path = get_file_name(source_path, None, None)
        self.assertEqual(new_path, USER_PATH + "/test.py")

    def test_get_file_name_no_change_relative(self):
        source_path = "/home/user/../test.py"
        new_path = get_file_name(source_path, None, None)
        self.assertEqual(new_path, "/home/test.py")

    def test_get_file_name_no_change_abs(self):
        source_path = "/home/test.py"
        new_path = get_file_name(source_path, None, None)
        self.assertEqual(new_path, "/home/test.py")

    def test_get_prov_file_format_invalid(self):
        file_name = "/test_file"
        self.assertIsNone(_get_prov_file_format(file_name))

    def test_get_prov_file_format_ttl(self):
        file_name = "/test_file.ttl"
        self.assertEqual(_get_prov_file_format(file_name), "turtle")

    def test_get_prov_file_format_rdf(self):
        file_name = "/test_file.rdf"
        self.assertEqual(_get_prov_file_format(file_name), "xml")

    def test_get_prov_file_format_json(self):
        file_name = "/test_file.json"
        self.assertEqual(_get_prov_file_format(file_name), "json-ld")

    def test_get_prov_file_format_n3(self):
        file_name = "/test_file.n3"
        self.assertEqual(_get_prov_file_format(file_name), "n3")

    def test_get_prov_file_format_other(self):
        file_name = "/test_file.other"
        self.assertEqual(_get_prov_file_format(file_name), "other")

    def test_get_file_format_no_ext(self):
        file_name = "/home/test"
        self.assertEqual(_get_file_format(file_name), None)

    def test_get_file_format(self):
        file_name = "/home/test.png"
        self.assertEqual(_get_file_format(file_name), "png")


if __name__ == "__main__":
    unittest.main()
