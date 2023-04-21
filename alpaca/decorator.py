"""
This module implements a function decorator to support provenance capture
during the execution of analysis scripts in Python.
"""

from functools import wraps
from collections.abc import Iterable
from importlib.metadata import version, PackageNotFoundError
import inspect
import ast
import datetime
import logging
import uuid

from alpaca.alpaca_types import FunctionExecution, FunctionInfo, Container
from alpaca.data_information import _ObjectInformation, _FileInformation
from alpaca.code_analysis.ast import _CallAST
from alpaca.code_analysis.source_code import _SourceCode
from alpaca.serialization import AlpacaProvDocument
from alpaca.utils.files import RDF_FILE_FORMAT_MAP
from alpaca.settings import _ALPACA_SETTINGS
from alpaca.ontology.annotation import OntologyInformation

from pprint import pprint


VAR_POSITIONAL = inspect.Parameter.VAR_POSITIONAL


# Create logger and set configuration
logger = logging.getLogger(__file__)
log_handler = logging.StreamHandler()
log_handler.setFormatter(logging.Formatter("[%(asctime)s] alpaca.decorator -"
                                           " %(levelname)s: %(message)s"))
logger.addHandler(log_handler)
logger.propagate = False


class Provenance(object):
    """
    Class to capture and store provenance information in Python scripts.

    The class is a callable object, to be used as a decorator to every function
    call from the script that will be tracked.

    Parameters
    ----------
    inputs : list of str
        Names of the arguments that are considered inputs to the function.
        An input is a variable or value with which the function will perform
        some computation or action. Arguments that only control the behavior
        of the function are considered parameters. The names can be for both
        positional or keyword arguments. Every argument that is not named in
        `inputs`, `container_input`, `file_input` or `file_output` will be
        considered as a parameter. If None, this parameter is ignored. If a
        function does not take any input (e.g., functions that generate data),
        `inputs` can be set to an empty list or None.
    file_input : list of str, optional
        Names of the arguments that represent file(s) read from the disk by
        the function. Their hashes will be computed and stored.
        Default: None
    file_output : list of str, optional
        Names of the arguments that represent file(s) write to the disk by
        the function. The hashes will be computed and stored.
        Default: None
    container_input : list of str, optional
        Names of the arguments that are containers of data (e.g., a list with
        data structures used by the function). Alpaca will track and identify
        the elements inside the container, instead of the container itself.
        Default: None
    container_output : bool, optional
        The function outputs data inside a container (e.g., a list). Alpaca
        will track and identify the elements inside the container, instead of
        the container itself.
        Default: False

    Attributes
    ----------
    active : bool
        If True, provenance tracking is active.
        If False, provenance tracking is suspended.
        This attribute is set using the :func:`activate`/:func:`deactivate`
        interface functions.
    history : list of FunctionExecution
        All events that were tracked. Each function call is structured in a
        named tuple `FunctionExecution` that stores:

        * 'function': `FunctionInfo` named tuple;
        * 'inputs': `dict` with the `DataObject` or `File` named tuples
          associated with every input value to the function;
        * 'params': `dict` with the positional/keyword argument names that are
          not data/file input/file output as keys. Values are the value of each
          argument as passed to the function call;
        * 'output': `dict` with the `DataObject` or `File` named tuples
          associated with the values returned by the function or files written
          to the disk;
        * 'arg_map': names of the positional arguments;
        * 'kwarg_map': names of the keyword arguments;
        * 'call_ast': `ast.AST` object containing the Abstract Syntax Tree
          of the code that generated the function call.
        * 'code_statement': `str` with the code statement calling the function.
        * 'time_stamp_start', 'time_stamp_end': `str` with the ISO
          representation of the start and end times of the function execution;
        * 'return_targets': names of the variables that store the function
          output(s) in the source code;
        * 'order': integer defining the order of this function call in the
           whole tracking history.
        * 'execution_id': `str` with the UUID of the particular function
           execution tracked.
    source_file : str
        Path to the script file being tracked.
    session_id : str
        Unique identifier (UUID) for this script execution.
    inputs : list
        Names of the function arguments that are considered inputs.
    file_inputs : list
        Names of the function arguments that are considered file inputs.
    file_outputs : list
        Names of the function arguments that are considered file outputs.
    container_inputs : list
        Names of the function arguments that are considered containers of
        data.
    container_output : bool
        True if the function outputs data in a container.

    Raises
    ------
    ValueError
        If `inputs` is not a list or not None.

    """

    active = False
    history = []
    session_id = None
    script_info = None

    source_file = None
    calling_frame = None

    _call_count = 0

    def __init__(self, inputs, file_input=None, file_output=None,
                 container_input=None, container_output=False):
        if inputs is None:
            inputs = []
        if file_input is None:
            file_input = []
        if file_output is None:
            file_output = []
        if container_input is None:
            container_input = []

        if not isinstance(inputs, list):
            raise ValueError("`inputs` must be a list")

        # Store the names of the arguments that are file input/outputs
        # or container inputs
        self.file_inputs = [f_input for f_input in file_input
                            if f_input is not None]
        self.file_outputs = [f_output for f_output in file_output
                             if f_output is not None]
        self.container_inputs = [c_input for c_input in container_input
                                 if c_input is not None]

        # Store the names of arguments that are inputs
        self.inputs = inputs

        self.container_output = container_output

    def _insert_static_information(self, tree, data_info, function,
                                   time_stamp):
        # Use an `ast.NodeVisitor` to find the `Call` node that corresponds to
        # the current `FunctionExecution`. It will fetch static relationships
        # between variables and attributes, and link to the inputs and outputs
        # of the function. The `data_info` object is passed, to use hash
        # memoization in case the hash of some object is already computed for
        # this call.
        ast_visitor = _CallAST(provenance_tracker=self, data_info=data_info,
                               function=function, time_stamp=time_stamp)
        ast_visitor.visit(tree)

    @staticmethod
    def _process_input_arguments(function, args, kwargs):
        # Inspect the arguments to extract the ones defined as inputs.
        # Values are stored in a dictionary with the argument name as key.
        # If signature inspection is not possible, the inputs are stored by
        # order in the function call, with the index as keys. The function
        # also returns the parameters (arguments that are not inputs), with
        # their default values.

        # Initialize dictionaries and lists
        input_data = {}
        input_args_names = []
        input_kwargs_names = []

        try:
            # Get the function signature and bind the arguments, obtaining a
            # dictionary with argument name as keys and argument value as
            # values
            fn_sig = inspect.signature(function)
            func_parameters = fn_sig.bind(*args, **kwargs)

            # Get the default argument values, to store them in case they
            # were not passed in the call
            default_args = {k: v.default
                            for k, v in fn_sig.parameters.items()
                            if v.default is not inspect.Parameter.empty}

            # For each item in the bound arguments dictionary...
            for arg_name, arg_value in func_parameters.arguments.items():

                # Get the description of the current argument by its name
                cur_parameter = \
                    func_parameters.signature.parameters[arg_name]

                # If this argument is one of possible default values, remove
                # it, since the user has passed a value explicitly
                if arg_name in default_args:
                    default_args.pop(arg_name)

                # If the argument is variable positional (i.e., *arg) we will
                # store its value in the input dictionary as the Container
                # named tuple. This signals that this argument's value is
                # multiple. Otherwise, we just store the argument value.
                if cur_parameter.kind != VAR_POSITIONAL:
                    input_data[arg_name] = arg_value
                else:
                    # Variable positional arguments are stored as
                    # the named tuple Container.
                    input_data[arg_name] = Container(arg_value)

                # Store the argument name in the appropriate list
                if arg_name in kwargs:
                    input_kwargs_names.append(arg_name)
                else:
                    input_args_names.append(arg_name)

            # Add the default argument names to the list of kwargs names
            input_kwargs_names.extend(default_args.keys())

        except ValueError:
            # Can't inspect signature. Append args/kwargs by order
            for arg_index, arg in enumerate(args):
                input_data[arg_index] = arg
                input_args_names.append(arg_index)

            # Keyword arguments index start after the last positional argument
            kwarg_start = len(input_data)
            for kwarg_index, kwarg in enumerate(kwargs,
                                                start=kwarg_start):
                input_data[kwarg_index] = kwarg
                input_kwargs_names.append(kwarg_index)

            # No default arguments
            default_args = {}

        return input_data, input_args_names, input_kwargs_names, default_args

    @staticmethod
    def _get_module_version(module, function_name):

        if not module.startswith("__main__"):
            # User-defined functions in the running script do not have a
            # version
            package = module.split(".")[0]
            try:
                return version(package)
            except PackageNotFoundError:
                # When running unit tests or using user-defined functions
                # imported from a source file
                return ""
        return ""

    def _get_calling_line_number(self, frame):
        # Get the line number of the current call.
        # For that, we need to find the frame containing the call, starting
        # from `frame`, which is the current frame being executed.
        lineno = None

        # Extract information and calling function name in `frame`
        frame_info = inspect.getframeinfo(frame)
        function_name = frame_info.function

        if function_name == '<listcomp>':
            # For list comprehensions, we need to check the frame above,
            # as this creates a function named <listcomp>. We use a while loop
            # in case of nested list comprehensions.
            while function_name == '<listcomp>':
                frame = frame.f_back
                frame_info = inspect.getframeinfo(frame)
                function_name = frame_info.function
        elif function_name == 'wrapper':
            # For functions with a decorator, we need to skip the decorator
            frame = frame.f_back
            frame_info = inspect.getframeinfo(frame)
            function_name = frame_info.function

        # If the frame corresponds to the script file and the tracked function,
        # we get the line number
        if (frame_info.filename == self.source_file and
                function_name == self._source_code.source_name):
            lineno = frame.f_lineno

        return lineno

    def _capture_code_and_function_provenance(self, lineno, function):

        # 1. Capture Abstract Syntax Tree (AST) of the call to the
        # function. We need to check the source code in case the
        # call spans multiple lines. In this case, we fetch the
        # full statement using the code analyzer.
        source_line = \
            self._source_code.extract_multiline_statement(lineno)
        ast_tree = ast.parse(source_line)
        logger.info(f"Line {lineno} -> {source_line}")

        # 2. Check if there is an assignment to one or more
        # variables. This will be used to identify if there are
        # multiple output nodes. This is needed because just
        # checking if `function_output` is tuple does not work if
        # the function is actually returning a tuple.
        return_targets = []
        if isinstance(ast_tree.body[0], ast.Assign):
            assign_target = ast_tree.body[0].targets[0]
            if isinstance(assign_target, ast.Tuple):
                return_targets = [target.id for target in
                                  assign_target.elts]
            elif isinstance(assign_target, ast.Name):
                return_targets = [assign_target.id]
            else:
                # This branch should not be reachable
                raise ValueError("Unknown assign target!")

        # 3. Extract function name and information
        module = getattr(function, '__module__')
        function_name = function.__qualname__
        module_version = self._get_module_version(module=module,
                                                  function_name=function_name)

        ontology_information = OntologyInformation(function) \
                if OntologyInformation.has_ontology(function) else None

        function_info = FunctionInfo(name=function_name, module=module,
                                     version=module_version,
                                     ontology=ontology_information)

        return source_line, ast_tree, return_targets, function_info

    def _capture_input_and_parameters_provenance(self, function, args, kwargs,
        ast_tree, function_info, time_stamp_start, builtin_object_hash):

        # 1. Extract the parameters passed to the function and store them in
        # the `input_data` dictionary.
        # Two separate lists with the names according to the arg/kwarg order
        # are also constructed, to map to the `args` and `keywords` fields
        # of the AST nodes. Also, the list of all arguments whose values taken
        # are defaults is returned as the `default_args` dictionary.

        input_data, input_args_names, input_kwargs_names, default_args = \
            self._process_input_arguments(function, args, kwargs)

        # 2. Create parameters/input descriptions for the graph.
        # Here the inputs, but not the parameters passed to the function, are
        # hashed using the `_ObjectInformation` object.
        # Inputs are defined by the parameter `inputs` when initializing the
        # decorator, and stored as the attribute `inputs`. If one parameter
        # is defined as a `file_input` in the initialization, a hash to the
        # file is obtained using the `_FileInformation` object. If one
        # parameter is defined as `container_input` in the initialization, its
        # elements are hashed and stored if the value is iterable.
        # After this step, all hashes and metadata of input parameters/files
        # are going to be stored in the dictionary `inputs`.

        data_info = _ObjectInformation(use_builtin_hash=builtin_object_hash)

        # Initialize parameter list with all default arguments that were not
        # passed to the function
        parameters = default_args

        inputs = {}
        for key, input_value in input_data.items():
            if key in self.inputs:
                if isinstance(input_value, Container):
                    # If the argument is multiple, hash each value
                    # tuple and store them inside a `Container` namedtuple so
                    # that we know this is a multiple input
                    var_input_list = []
                    for var_arg in input_value.elements:
                        var_input_list.append(data_info.info(var_arg))
                    inputs[key] = Container(tuple(var_input_list))
                else:
                    inputs[key] = data_info.info(input_value)

            elif key in self.file_inputs:
                # Input is from a file. Hash using `_FileInformation`
                inputs[key] = _FileInformation(input_value).info()

            elif key in self.container_inputs and \
                    isinstance(input_value, Iterable):
                # This is a container. Iterate over elements and store inside
                # a `Container` namedtuple
                container_elements = []
                for element in input_value:
                    container_elements.append(data_info.info(element))
                inputs[key] = Container(tuple(container_elements))

            elif key not in self.file_outputs:
                # The remainder argument is also not an output file, so this
                # is a parameter to the function.
                parameters[key] = input_value

        # 3. Analyze AST and fetch static relationships in the
        # input/output and other variables/objects in the script
        self._insert_static_information(tree=ast_tree, data_info=data_info,
                                        function=function_info.name,
                                        time_stamp=time_stamp_start)

        return inputs, parameters, input_args_names, input_kwargs_names, \
            input_data

    def _capture_output_provenance(self, function_output, return_targets,
                                   input_data, builtin_object_hash):

        # In case in-place operations were performed, lets not use
        # memoization
        data_info = _ObjectInformation(use_builtin_hash=builtin_object_hash)

        # 6. Create hash for the output using `_ObjectInformation` to follow
        # individual returns. The hashes will be stored in the `outputs`
        # dictionary, with the index as the order of each returned object.
        # If the decorator was initialized with `container_output=True`, the
        # elements of the output will be hashed, if iterable.
        outputs = {}
        if self.container_output and isinstance(function_output, Iterable):
            iterator = enumerate(function_output)
        else:
            if len(return_targets) < 2:
                function_output = [function_output]
            iterator = enumerate(function_output)

        for index, item in iterator:
            outputs[index] = data_info.info(item)

        # If there is a file output as defined in the decorator
        # initialization, create the hash and add as output using
        # `_FileInformation`. These outputs will be identified by the key
        # `file.X`, where X is an integer with the order of the file output
        if self.file_outputs:
            for idx, file_output in enumerate(self.file_outputs):
                outputs[f"file.{idx}"] = \
                    _FileInformation(input_data[file_output]).info()

        return outputs

    def __call__(self, function):

        @wraps(function)
        def wrapped(*args, **kwargs):

            builtin_object_hash = _ALPACA_SETTINGS[
                'use_builtin_hash_for_module']
            logging.debug(f"Builtin object hash: {builtin_object_hash}")

            lineno = None

            # If capturing provenance, get the code, function, inputs and
            # parameter information, before executing the function
            if Provenance.active:

                # For functions that are used inside other decorated functions,
                # or recursively, check if the calling frame is the one being
                # tracked. If this call comes from the frame tracked, we will
                # get the line number. Otherwise, the line number will be
                # None, and the provenance tracking block will be skipped.
                try:
                    frame = inspect.currentframe().f_back
                    lineno = self._get_calling_line_number(frame)
                finally:
                    del frame

                if lineno:
                    # Get the start time stamp
                    time_stamp_start = datetime.datetime.utcnow().isoformat()

                    # Increment the global call counter
                    Provenance._call_count += 1

                    # Create execution ID
                    execution_id = str(uuid.uuid4())

                    # Capture code and function information
                    source_line, ast_tree, return_targets, function_info = \
                        self._capture_code_and_function_provenance(
                            lineno=lineno, function=function)

                    # Capture input and parameter information
                    inputs, parameters, input_args_names, \
                        input_kwargs_names, input_data = \
                            self._capture_input_and_parameters_provenance(
                                function=function, args=args, kwargs=kwargs,
                                ast_tree=ast_tree, function_info=function_info,
                                time_stamp_start=time_stamp_start,
                                builtin_object_hash=builtin_object_hash)

            # Call the function
            function_output = function(*args, **kwargs)

            # If capturing provenance, resume capturing the output information
            if Provenance.active and lineno:

                # Capture output information
                outputs = self._capture_output_provenance(
                    function_output=function_output,
                    return_targets=return_targets, input_data=input_data,
                    builtin_object_hash=builtin_object_hash)

                # Get the end time stamp
                time_stamp_end = datetime.datetime.utcnow().isoformat()

                # Create FunctionExecution tuple
                function_execution = FunctionExecution(
                    function=function_info,
                    input=inputs,
                    params=parameters,
                    output=outputs,
                    arg_map=input_args_names,
                    kwarg_map=input_kwargs_names,
                    call_ast=ast_tree,
                    code_statement=source_line,
                    time_stamp_start=time_stamp_start,
                    time_stamp_end=time_stamp_end,
                    return_targets=return_targets,
                    order=Provenance._call_count,
                    execution_id=execution_id)

                # Add to the history.
                # The history will be the base to generate the graph and
                # PROV document.
                Provenance.history.append(function_execution)

            return function_output

        return wrapped

    @classmethod
    def _get_script_variable(cls, name):
        # Access to variable values in the tracked code by name.
        return cls.calling_frame.f_locals[name]

    @classmethod
    def _set_calling_frame(cls, frame):
        """
        This method stores the frame of the code being tracked, and
        extract several information that is needed for capturing provenance.

        A `_SourceCode` object is created, to provide an interface to
        retrieve information from the code (e.g., statements given a line
        number).

        It also initializes a unique ID for the script run, and stores the
        information regarding the script file (`File` named tuple).

        Parameters
        ----------
        frame : inspect.frame
            Frame object returned by the `inspect` module. This must
            correspond to the namespace where provenance tracking was
            activated. This is automatically fetched by the interface function
            :func:`activate`.
        """

        # Store the reference to the calling frame
        cls.calling_frame = frame

        # Get the file name and function associated with the frame
        cls.source_file = inspect.getfile(frame)

        # Create a _SourceCode instance with the frame information,
        # so that we can capture provenance information later
        cls._source_code = _SourceCode(frame)

        # Create a unique identifier for the session and store script info
        cls.session_id = str(uuid.uuid4())
        cls.script_info = _FileInformation(cls.source_file).info()

    @classmethod
    def get_prov_info(cls):
        """
        Returns the representation of the captured provenance information
        according to the Alpaca ontology based on the W3C PROV-O.

        Returns
        -------
        serialization.AlpacaProvDocument
        """

        prov_document = AlpacaProvDocument()
        prov_document.add_history(script_info=cls.script_info,
                                  session_id=cls.session_id,
                                  history=cls.history)
        return prov_document

    @classmethod
    def clear(cls):
        """
        Clears all the history and reset the execution counter to zero.
        """
        cls.history.clear()
        cls._call_count = 0


##############################################################################
# Interface functions
##############################################################################

def activate(clear=False):
    """
    Activates provenance tracking within the script.

    Parameters
    ----------
    clear : bool, optional
        If True, the history is cleared and execution counter is reset to
        zero.
        Default: False
    """
    if clear:
        Provenance.clear()

    # To access variables in the same namespace where the function is called,
    # and get information from the source code, the previous frame in the
    # stack needs to be saved.
    Provenance._set_calling_frame(inspect.currentframe().f_back)
    Provenance.active = True


def deactivate():
    """
    Deactivates provenance tracking within Elephant.
    """
    Provenance.calling_frame = None
    Provenance.active = False


def print_history():
    """
    Print all executions in the provenance track history.
    """
    pprint(Provenance.history)


def save_provenance(file_name=None, file_format='ttl'):
    """
    Serialize provenance information according to the Alpaca ontology based
    on the W3C PROV Ontology (PROV-O).

    Parameters
    ----------
    file_name : str or Path-like, optional
        Destination file to serialize the provenance information.
        If None, the function will return a string containing the provenance
        information in the specified format.
        Default: None
    file_format : {'json-ld', 'n3', 'nt', 'hext', 'pretty-xml', 'trig', 'turtle', 'longturtle', 'xml', 'ttl', 'rdf', 'json'}
        Format into which the provenance data is serialized. The formats are
        the ones accepted by RDFLib. Some shortucts are defined for common
        file extensions:

        * 'ttl': Turtle
        * 'rdf': RDF/XML
        * 'json': JSON-LD

        Default: 'ttl'

    Returns
    -------
    str or None
        If `file_name` is None, the function returns the PROV information as
        a string. If a file destination was informed, the return is None.
    """
    if file_format in RDF_FILE_FORMAT_MAP:
        file_format = RDF_FILE_FORMAT_MAP[file_format]

    prov_document = Provenance.get_prov_info()
    prov_data = prov_document.serialize(file_name, file_format=file_format)
    return prov_data
