"""
This module implements classes to identify Python objects through the analysis
of nodes from an Abstract Syntax Tree, and generates the relationships
between them. The classes support building a hierarchical tree describing
the child/parent relationships between the objects.

Example
-------

For `spiketrains[0]`, the object `spiketrains[0]` is
represented by an `ast.Subscript` AST node. Its information is retrieved by a
`_SubscriptRelationship` object in this module. This will provide the actual
`spiketrains[0]` Python object and an `DataObject` tuple with the index
information (i.e., `0`).

The `spiketrains` container is represented by an `ast.Name` AST node,
whose information is retrieved by the `_NameRelationship` object.
When creating `_NameRelationship`, the `child` parameter will be the
`_SubscriptRelationship` obtained previously for the indexing operation (i.e.,
`spiketrains[0]`).

Therefore, the object tree is created. After the tree is created, the
appropriate `FunctionExecution` named tuples to express those relationships
in the provenance history are created through the `get_function_execution`
method.
"""

import ast
from alpaca.alpaca_types import FunctionExecution, FunctionInfo
import uuid


class _StaticRelationship(object):
    """
    Base class for relationships extracted through static code analysis.

    The information from a single Abstract Syntax Tree node is extracted and
    the reference to the actual Python object that the node represents is
    stored, as well as its information as the `DataObject` named tuple.

    Parameters
    ----------
    node : ast.AST
        Abstract Syntax Tree node that represents the object.
        The subclass varies for each operation.
    time_stamp : datetime
        Time stamp associated with this operation.
    child : _StaticRelationship, optional
        A `_StaticRelationship` object that is owned by the one being created.
        If a node in the Abstract Syntax Tree contains other nodes that
        describe a Python object being tracked, the `_StaticRelationship`
        object obtained from this node is the parent.

        Example: for `spiketrains[0]`, the `_SubscriptRelationship` associated
        with `ast.Subscript` that represents `spiketrains[0]` is the child of
        the `_NameRelationship` associated with the `ast.Name` that represents
        `spiketrains`. In this `ast.Name`, `ast.Subscript` is a value of the
        `
        Default: None.

    Attributes
    ----------
    object_info : alpaca_types.DataObject
        Named tuple describing the Python object associated with this
        `_StaticRelationship` instance.
    parent : _StaticRelationship
        `_StaticRelationship` object that owns this instance.
    value : object
        Reference to the actual Python object associated with this
        `_StaticRelationship` instance.

    Raises
    ------
    TypeError
        If `node` is not of the type describing the operation represented
        by the `_StaticRelationship` object.

    Example
    -------
    For `spiketrains[0]`, a `_SubscriptRelationship` object will have
    :attr:`value` pointing to `spiketrains[0]`, and a :attr:`parent` pointing
    to a `_NameRelationship` object whose :attr:`value` points to
    `spiketrains`. For `_NameRelationship`, :attr:`parent` is None as this is
    the root of the relationships.
    """

    _operation = None
    _node_type = None

    def __init__(self, node, time_stamp, child=None):
        if not isinstance(node, self._node_type):
            raise TypeError("AST node must be of type '"
                            f"{type(self._node_type)}'")
        self.parent = None
        self._node = node
        if child is not None:
            child.set_parent(self)
        self.object_info = None
        self.time_stamp = time_stamp

    def set_parent(self, parent):
        self.parent = parent

    @property
    def value(self):
        """
        Returns the Python object associated with this instance.
        """
        raise NotImplementedError

    def _get_params(self):
        raise NotImplementedError

    def get_function_execution(self):
        """
        Returns a `FunctionExecution` named tuple describing the relationships
        between parent and child nodes. The `params` element will contain the
        relevant information of the relationship (e.g., slice range, index
        number, or attribute name). The function name in the `FunctionInfo`
        named tuple will be the operation name (e.g., 'attribute',
        'subscript', or 'variable'.
        """

        params = self._get_params()
        input_object = self.parent.object_info if self.parent is not None \
            else None
        output_object = self.object_info

        execution_id = str(uuid.uuid4())

        return FunctionExecution(
            function=FunctionInfo(name=self._operation,
                                  module="",
                                  version=""),
            input={0: input_object},
            params=params,
            output={0: output_object},
            arg_map=None,
            kwarg_map=None,
            call_ast=self._node,
            code_statement=None,
            time_stamp_start=self.time_stamp,
            time_stamp_end=self.time_stamp,
            return_targets=[],
            order=None,
            execution_id=execution_id)


class _NameRelationship(_StaticRelationship):
    """
    Static relationship that represents an `ast.Name` Abstract Syntax Tree
    node.

    This is supposed to be the first level of a tree describing the
    dependencies between the objects, and maps to a variable in the script.

    The node must be previously modified to include the reference to the
    Python object associated with the variable, and a `DataObject` named tuple
    with the information from the object.
    """

    _operation = 'variable'
    _node_type = ast.Name

    def __init__(self, node, time_stamp, child=None):
        super(_NameRelationship, self).__init__(node, time_stamp, child)
        self.object_info = node.object_info

    @property
    def value(self):
        return self._node.instance

    def _get_params(self):
        return None


class _SubscriptRelationship(_StaticRelationship):
    """
    Static relationship that represents an `ast.Subscript` Abstract Syntax
    Tree node.

    This represents a subscripting operation in the script.
    """

    _operation = 'subscript'
    _node_type = ast.Subscript

    def __init__(self, node, time_stamp, child):
        super(_SubscriptRelationship, self).__init__(node, time_stamp, child)
        self._slice = self._get_slice(node.slice)

    @staticmethod
    def _get_slice(slice_node):
        # Extracts index or slice information from an `ast.Slice` or
        # `ast.Index` nodes that are the `slice` attribute of `ast.Subscript`.
        # Returns the slice/index value, that will be used to fetch the
        # actual Python object returned by the subscript operation.

        if isinstance(slice_node, ast.Index):

            # Integer or string indexing
            if isinstance(slice_node.value, ast.Num):
                index_value = int(slice_node.value.n)
            elif isinstance(slice_node.value, ast.Str):
                index_value = slice_node.value.s
            elif isinstance(slice_node.value, ast.Name):
                from alpaca.decorator import Provenance
                index_value = Provenance._get_script_variable(slice_node.value.id)
            elif isinstance(slice_node.value, ast.UnaryOp) and \
                isinstance(slice_node.value.op, ast.USub):
                # Negative indexing
                index_value = -int(slice_node.value.operand.n)
            else:
                raise TypeError("Operation not supported")

            return index_value

        # Required for newer Python versions
        if isinstance(slice_node, ast.Constant):
            index_value = slice_node.value
            return index_value

        if isinstance(slice_node, ast.UnaryOp) and \
                isinstance(slice_node.op, ast.USub):
            # Negative indexing
            return -int(slice_node.operand.n)

        if isinstance(slice_node, ast.Name):
            from alpaca.decorator import Provenance
            index_value = Provenance._get_script_variable(slice_node.id)
            return index_value

        if isinstance(slice_node, ast.Slice):
            # Slicing
            stop = getattr(slice_node, 'upper')
            start = getattr(slice_node, 'lower', None)
            step = getattr(slice_node, 'step', None)

            stop = int(stop.n) if stop is not None else None
            start = int(start.n) if start is not None else None
            step = int(step.n) if step is not None else None

            return slice(start, stop, step)

    def _get_params(self):
        params = {}
        if isinstance(self._slice, slice):
            start = self._slice.start
            stop = self._slice.stop
            step = self._slice.step

            params['slice'] = f":{stop}" if stop is not None else ":"
            if start is not None:
                params['slice'] = f"{start}{params['slice']}"
            if step is not None:
                params['slice'] += f":{step}"
        else:
            params['index'] = self._slice

        return params

    @property
    def value(self):
        return self.parent.value[self._slice]


class _AttributeRelationship(_StaticRelationship):
    """
    Static relationship that represents an `ast.Attribute` Abstract Syntax
    Tree node.

    This represents accessing an object attribute using dot '.' operation in
    the script.
    """

    _operation = 'attribute'
    _node_type = ast.Attribute

    def __init__(self, node, time_stamp, child=None):
        super(_AttributeRelationship, self).__init__(node, time_stamp, child)

    def _get_params(self):
        return {'name': self._node.attr}

    @property
    def value(self):
        return getattr(self.parent.value, self._node.attr)
