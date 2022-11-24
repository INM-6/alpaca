import unittest

import inspect
from functools import wraps
from alpaca.code_analysis.source_code import _SourceCode


# Dummy functions and variables
# They are used inside the tests to provide an executable code that can be
# analyzed by the _SourceCode class that is being tested here

def function_call(*args):
    return


def decorator(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        return function(*args, **kwargs)
    return wrapper


arg11 = arg12 = arg21 = arg22 = arg31 = arg32 = arg41 = arg42 = arg51 \
    = arg52 = None


# To hold the source code object (dummy for the Provenance decorator)

class Class:
    source_code = None


# Mimics the behavior of the activate function of Alpaca, to get the frame of
# the scope where it was called

def activate():
    Class.source_code = _SourceCode(inspect.currentframe().f_back)


# Expected results for each statement

RES1 = 'res1 = function_call(arg11, arg12)'
RES2 = """res2 = function_call(arg21,
                                 arg22)"""
RES3 = """res3 = \\
                function_call(arg31, arg32)"""
RES4 = 'res4 = function_call(arg41, arg42)'
RES5 = 'res5 = function_call(arg51, arg52)'
RES6 = 'res6 = function_call(arg11, arg21)'


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
            59: None,
            60: "activate()",
            61: None,
            62: RES1,
            63: None,
            64: RES2, 65: RES2,
            66: None,
            67: RES3, 68: RES3,
            69: None,
            70: RES4,
            71: RES5,
            72: None,
            73: None,
            74: RES6, 75: None,
        }

        for line, expected_statement in expected_statements.items():
            with self.subTest(f"line: {line}, "
                              f"expected: {expected_statement}"):
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
            106: None,
            107: RES1,
            108: None,
            109: RES2, 110: RES2,
            111: None,
            112: RES3, 113: RES3,
            114: "activate()",
            115: None,
            116: RES4,
            117: RES5,
            118: None,
            119: None,
            120: RES6, 121: None
        }

        for line, expected_statement in expected_statements.items():
            with self.subTest(f"line: {line}, "
                              f"expected: {expected_statement}"):
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
            152: None,
            153: "activate()",
            154: None,
            155: RES1,
            156: None,
            157: RES2, 158: RES2,
            159: None,
            160: RES3, 161: RES3,
            162: None,
            163: RES4,
            164: RES5,
            165: None,
            166: None,
            167: RES6, 168: None
        }

        for line, expected_statement in expected_statements.items():
            with self.subTest(f"line: {line}, "
                              f"expected: {expected_statement}"):
                self.assertEqual(
                    source_code.extract_multiline_statement(line),
                    expected_statement
                )


class CodeAnalyzerWithBlocksTestCase(unittest.TestCase):

    def test_for(self):

        def main():
            activate()

            res1 = function_call(arg11, arg12)

            for arg in range(5):
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
            202: None,
            203: "activate()",
            204: None,
            205: RES1,
            206: None, 207: None,
            208: RES2, 209: RES2,
            210: None,
            211: RES3, 212: RES3,
            213: None,
            214: RES4,
            215: RES5,
            216: None,
            217: None,
            218: RES6, 219: None
        }

        for line, expected_statement in expected_statements.items():
            with self.subTest(f"line: {line}, "
                              f"expected: {expected_statement}"):
                self.assertEqual(
                    source_code.extract_multiline_statement(line),
                    expected_statement
                )

    def test_if(self):

        def main():
            activate()

            res1 = function_call(arg11, arg12)

            if arg21 is None:
                res2 = function_call(arg21,
                                 arg22)

            elif arg31 is None:
                res3 = \
                function_call(arg31, arg32)

            else:
                res4 = function_call(arg41, arg42)
            res5 = function_call(arg51, arg52)

            # With comment
            res6 = function_call(arg11, arg21)

        main()
        source_code = Class.source_code

        expected_statements = {
            250: None,
            251: "activate()",
            252: None,
            253: RES1,
            254: None, 255: None,
            256: RES2, 257: RES2,
            258: None, 259: None,
            260: RES3, 261: RES3,
            262: None, 263: None,
            264: RES4,
            265: RES5,
            266: None,
            267: None,
            268: RES6, 269: None
        }

        for line, expected_statement in expected_statements.items():
            with self.subTest(f"line: {line}, "
                              f"expected: {expected_statement}"):
                self.assertEqual(
                    source_code.extract_multiline_statement(line),
                    expected_statement
                )


if __name__ == "__main__":
    unittest.main()
