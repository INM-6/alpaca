import unittest

import inspect
from functools import wraps
from alpaca.code_analysis.source_code import _SourceCode


# Dummy functions and variables

def function_call(*args):
    return

def decorator(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return function(*args, **kwargs)
    return wrapper

arg11 = arg12 = arg21 = arg22 = arg31 = arg32 = arg41 = arg42 = arg51 \
    = arg52 = None

# Mimics the behavior of the activate function, to get the frame of the
# scope where it was called
def activate():
    Class.source_code = _SourceCode(inspect.currentframe().f_back)

# To hold the source code object
class Class:
    source_code = None


# Expected results for each statement

RES1 = 'res1 = function_call(arg11, arg12)'
RES2 = """res2 = function_call(arg21,
                                 arg22)"""
RES3 = """res3 = \\
                function_call(arg31, arg32)"""
RES4 = 'res4 = function_call(arg41, arg42)'
RES5 = 'res5 = function_call(arg51, arg52)'
RES6 = 'res6 = function_call(arg11, arg21)'


def compare_statements(statement1, statement2):
    return statement1.strip() == statement2.strip()


class CodeAnalyzerTestCase(unittest.TestCase):

    def setUp(self):
        Class.source_code = None

    def test_function_main(self):

        def main():
            activate()

            res1 = function_call(arg11, arg12)

            res2 = function_call(arg21,
                                 arg22)

            res3 = \
                function_call(arg31, arg32)

            res4 = function_call(arg41, arg42)
            res5 = function_call(arg51, arg52)

            # With comment
            res6 = function_call(arg11, arg21)

        main()
        source_code = Class.source_code

        expected_statements = {
            55: None,
            56: "activate()",
            57: None,
            58: RES1,
            59: None,
            60: RES2, 61: RES2,
            62: None,
            63: RES3, 64: RES3,
            65: None,
            66: RES4,
            67: RES5,
            68: None,
            69: None,
            70: RES6
        }

        for line, expected_statement in expected_statements.items():
            with self.subTest(f"line = {line}, "
                              f"expected = {expected_statement}"):
                self.assertEqual(
                    source_code.extract_multiline_statement(line),
                    expected_statement
                )

    def test_function_activate_middle(self):

        def main():
            res1 = function_call(arg11, arg12)

            res2 = function_call(arg21,
                                 arg22)

            res3 = \
                function_call(arg31, arg32)
            activate()

            res4 = function_call(arg41, arg42)
            res5 = function_call(arg51, arg52)

            # With comment
            res6 = function_call(arg11, arg21)

        main()
        source_code = Class.source_code

        expected_statements = {
            102: None,
            103: RES1,
            104: None,
            105: RES2, 106: RES2,
            107: None,
            108: RES3, 109: RES3,
            110: "activate()",
            111: None,
            112: RES4,
            113: RES5,
            114: None,
            115: None,
            116: RES6
        }

        for line, expected_statement in expected_statements.items():
            with self.subTest(f"line = {line}, "
                              f"expected = {expected_statement}"):
                self.assertEqual(
                    source_code.extract_multiline_statement(line),
                    expected_statement
                )

    def test_function_decorator(self):

        @decorator
        def main():
            activate()

            res1 = function_call(arg11, arg12)

            res2 = function_call(arg21,
                                 arg22)

            res3 = \
                function_call(arg31, arg32)

            res4 = function_call(arg41, arg42)
            res5 = function_call(arg51, arg52)

            # With comment
            res6 = function_call(arg11, arg21)

        main()
        source_code = Class.source_code

        expected_statements = {
            148: None,
            149: "activate()",
            150: None,
            151: RES1,
            152: None,
            153: RES2, 154: RES2,
            155: None,
            156: RES3, 157: RES3,
            158: None,
            159: RES4,
            160: RES5,
            161: None,
            162: None,
            163: RES6
        }

        for line, expected_statement in expected_statements.items():
            with self.subTest(f"line = {line}, "
                              f"expected = {expected_statement}"):
                self.assertEqual(
                    source_code.extract_multiline_statement(line),
                    expected_statement
                )


if __name__ == "__main__":
    unittest.main()
