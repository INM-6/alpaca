"""
This module defines named tuples that are used to structure the information
throughout Alpaca.
"""

from collections import namedtuple


# NAMED TUPLES TO STORE PROVENANCE INFORMATION OF EACH CALL

# In `FunctionExecution`:
#   `function`: a `FunctionInfo` named tuple;
#   `input` and `output`: dictionaries with `DataObject` or `File` named
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
#        function were stored;
#    `order`: integer defining the order of this function call in the whole
#        tracking history;
#    `execution_id`: UUID of this function call.

FunctionExecution = namedtuple('FunctionExecution', ('function',
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
                                                     'order',
                                                     'execution_id')
                               )

FunctionInfo = namedtuple('FunctionInfo', ('name', 'module', 'version',))


# NAMED TUPLE TO STORE ARGUMENTS THAT ARE CONTAINERS

# This can be elements inside an iterator (such as a list) but also
# variable arguments that are defined in the form `*args` in the function
# definition. Each element of the `Container` named tuple will be stored as
# individual `DataObject` named tuples in `Container.elements` dictionary,
# according to their order

Container = namedtuple('Container', 'elements')


# NAMED TUPLES TO STORE HASHES AND INFORMATION ABOUT OBJECTS

# `DataObject` is for Python objects, and `File` is for files stored in
# the disk.

DataObject = namedtuple('DataObject', ('hash', 'hash_method', 'type', 'id',
                                       'details', 'value'))

File = namedtuple('File', ('hash', 'hash_type', 'path'))
