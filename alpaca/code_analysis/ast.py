"""
This module implements classes to extract and work with the information
obtained from the nodes of an Abstract Syntax Tree (AST) describing the code
associated with a given function call within the script.

Example
-------

Consider the statement below:

>>> isi_times = isi(block.segments[0].spiketrains[0])

The object that was input to the `isi` function is the first element of the
list `spiketrains`, that is an attribute from the first element of the list
`segments` from the `block` object.

The `_CallAST` object in this module takes the `Call` AST node associated with
that statement, and all these attribute/indexing operations are reconstructed,
so that the actual input to the function is described with respect to its
hierarchical membership to the `block` object. For this, the
`static_relationship_tree._StaticRelationship` objects are used.

In the end, after processing the AST `Call` node, the attribute/indexing
operations are added as individual `FunctionExecution` tuples to the
provenance history in the decorator, with the details to reconstruct the
static relationships, and with the intermediate objects added to the
provenance track.

The operations currently analyzed correspond to the `Name`, `Attribute` and
`Subscript` AST Nodes.

The classes defined in this module are not intended to be used directly by
the user, but are used internally by the `decorator.Provenance` decorator.
"""

import ast
import itertools

from alpaca.code_analysis.static_relationship_tree import (
    _AttributeRelationship, _NameRelationship, _SubscriptRelationship)


class _NameAST(ast.NodeTransformer):
    """
    NodeTransformer to find all root variables that are loaded in an
    Abstract Syntax Tree (i.e., identified by `ast.Name` nodes).

    The reference to the actual Python object is stored in the transformed
    node as the :attr:`instance`, and the object information is stored in the
    :attr:`object_info` attribute.

    Parameters
    ----------
    provenance_tracker : decorator.Provenance
        Reference to the Alpaca provenance tracker decorator.
    data_info : data_information._ObjectInformation
        Instance to the class used to hash and get information of objects in
        Alpaca.
    """

    provenance_tracker = None

    def __init__(self, provenance_tracker, data_info):
        super(_NameAST, self).__init__()
        self.provenance_tracker = provenance_tracker
        self.data_info = data_info

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            # If this is a node where the variable is accessed, get the
            # actual object from the tracked frame, and store the object
            # reference and info
            instance = self.provenance_tracker._get_script_variable(node.id)
            setattr(node, 'instance', instance)
            setattr(node, 'object_info', self.data_info.info(instance))
            return node
        return node


class _CallAST(ast.NodeVisitor):
    """
    NodeVisitor to inspect and fetch subscript/attribute relationships
    in the call to the function that is being tracked (i.e., an `ast.Call`
    node).

    This will not transform the node, only add `FunctionExecution` named
    tuples to the history.

    Parameters
    ----------
    provenance_tracker : decorator.Provenance
        Reference to the provenance tracker decorator with the history.
    data_info : data_information._ObjectInformation
        Instance to the class used to hash and get information of the objects
        in Alpaca.
    function : str
        Name of the function being tracked.
    time_stamp : datetime
        Timestamp of the current function execution.
    """

    def __init__(self, provenance_tracker, data_info, function, time_stamp):
        super(_CallAST, self).__init__()
        self.provenance_tracker = provenance_tracker
        self.function = function
        self.data_info = data_info
        self.time_stamp = time_stamp

    def visit_Call(self, node):

        # In case of initializers, the AST function name will not have
        # `__init__` in the method name
        func_name = self.function[:-9] \
            if self.function.endswith(".__init__") else self.function

        # Check if the Call is for the function being executed.
        # If a function is called using a namespace or as a method, the `func`
        # attribute will be `ast.Attribute`.
        function_in_execution = False
        if isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            function_in_execution = func_name.endswith(f".{attr_name}")
        elif isinstance(node.func, ast.Name):
            function_in_execution = node.func.id == func_name

        if function_in_execution:
            # Fetch static information of Attribute and Subscript nodes that
            # were inputs. This should capture hierarchical information for
            # inputs that are class members or items in accessed in iterables
            for position, arg_node in enumerate(
                    itertools.chain(node.args, node.keywords)):

                if isinstance(arg_node, (ast.Subscript, ast.Attribute)):
                    _process_subscript_or_attribute(
                        node=arg_node,
                        provenance_tracker=self.provenance_tracker,
                        data_info=self.data_info,
                        time_stamp=self.time_stamp)
        else:
            # Otherwise just process the node with the generic visitor
            self.generic_visit(node)


def _fetch_object_tree(root_node, time_stamp):
    # Iterate recursively the syntax tree of `root_node`, building a
    # hierarchical tree using `_StaticRelationship` objects. This will fetch
    # the actual Python objects for every single attribute/subscript/name
    # operations.

    def _extract(node, child=None):
        if isinstance(node, ast.Subscript):
            subscript = _SubscriptRelationship(node, time_stamp, child)
            _extract(node.value, child=subscript)
            return subscript

        if isinstance(node, ast.Attribute):
            attribute = _AttributeRelationship(node, time_stamp, child)
            _extract(node.value, child=attribute)
            return attribute

        if isinstance(node, ast.Name):
            name = _NameRelationship(node, time_stamp, child)
            return name

    return _extract(root_node)


def _build_object_tree_provenance(object_tree, provenance_tracker, data_info):
    # Iterate recursively through a hierarchical tree of `_StaticRelationship`
    # objects representing the child/parent relationships between the objects,
    # and build the `FunctionExecution` tuples and store them in the history
    # of the provenance tracker decorator.

    def _get_object_info_and_store(tree_node):
        if tree_node.object_info is None:
            # Get info/hash if needed
            tree_node.object_info = data_info.info(tree_node.value)
        if tree_node.parent is not None:
            # Insert provenance information
            if tree_node.parent.object_info is None:
                # Get info/hash if needed
                tree_node.parent.object_info = data_info.info(
                    tree_node.parent.value)
            provenance_tracker.history.append(
                tree_node.get_function_execution())
            _get_object_info_and_store(tree_node.parent)

    _get_object_info_and_store(object_tree)


def _process_subscript_or_attribute(node, provenance_tracker, data_info,
                                    time_stamp):
    # From the AST starting from `node` (either `ast.Subscript` or
    # `ast.Attribute), find root variable (an `ast.Name` node), get the
    # info/hash of the associated Python object, and include reference in the
    # `ast.Name` node
    name_visitor = _NameAST(provenance_tracker, data_info)
    name_visitor.visit(node.value)

    # Fetch object references from the AST tree of `node`, and create the
    # tree of `_StaticRelationship` objects
    object_tree = _fetch_object_tree(node, time_stamp)

    # Insert provenance operations into the decorator history in
    # `provenance_tracker`, and get the remaining info/hashes if necessary
    _build_object_tree_provenance(object_tree, provenance_tracker, data_info)
