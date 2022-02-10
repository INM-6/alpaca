"""
This module defines named tuples that are used to structure the informatoin
throughout Alpaca.

"""

from collections import namedtuple


# NAMED TUPLES TO STORE PROVENANCE INFORMATION OF EACH CALL

# In `AnalysisStep`:
#   `function`: a `FunctionInfo` named tuple;
#   `input` and `output`: dictionaries with `ObjectInfo` or `FileInfo`
#        tuples as values, describing the objects for the input and the
#        output of the function, respectively;
#    `arg_map`: names of the positional arguments in the function definition;
#    `kwarg_map`: names of the keyword arguments in the function definition;
#    `call_ast`: `ast.Call` node for the current function call;
#    `code_statement`: string containing the script statement that originated
#        this function call;
#    `time_stamp_start` and `time_stamp_end`: ISO datetime values as strings,
#        with the start and end times of the function execution, respectively;
#    `return_targets`: names of the variables where the outputs of the
#        function were stored.
#    `order`: integer defining the order of this function call in the whole
#        tracking history.

AnalysisStep = namedtuple('AnalysisStep', ('function',
                                           'input',
                                           'params',
                                           'output',
                                           'arg_map',
                                           'kwarg_map',
                                           'call_ast',
                                           'code_statement',
                                           'time_stamp_start',
                                           'time_stamp_end',
                                           'return_targets',
                                           'order')
                          )


FunctionInfo = namedtuple('FunctionInfo', ('name', 'module', 'version'))


# NAMED TUPLE TO STORE VARIABLE ARGUMENTS

# Variable arguments are defined in the form `*args` in the function
# definition. Each element of variable argument tuple will be stored as
# individual `ObjectInfo` named tuples in `VarArgs.args` dictionary,
# according to their order

VarArgs = namedtuple('VarArgs', 'args')


# NAMED TUPLES TO STORE HASHES AND INFORMATION ABOUT OBJECTS

# `ObjectInfo` is for Python objects, and `FileInfo` is for files stored in
# the disk.

ObjectInfo = namedtuple('ObjectInfo', ('hash', 'type', 'id', 'details'))

FileInfo = namedtuple('FileInfo', ('hash', 'hash_type', 'path'))
