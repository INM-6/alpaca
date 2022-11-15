"""
This module implements a class to store and fetch information from the source
code of the frame that activated provenance tracking.

The main purpose is to retrieve the full multiline statements that generated
the call to a tracked function.

The class defined in this module is not intended to be used directly by
the user, but is used internally by the `decorator.Provenance` decorator.
"""

import inspect
import ast
import numpy as np


class _SourceCode(object):
    """
    Stores the source code of the frame that activated provenance tracking,
    and provides methods for retrieving execution statements by line number.

    Parameters
    ----------
    frame : inspect.frame
        The frame of the scope where provenance tracking was activated,
        from which the source code will be fetched.

    Attributes
    ----------
    source_name : str
        Name of the function that has the source code from `frame`.
        If this is the main script, the value will be '<module>'.
    source_lineno : str
        Absolute line number in the script file where the code starts.
    ast_tree : ast.Node
        Parsed AST tree of the source code from `frame`.
    source_code : np.ndarray
        Lines of the code from `frame`.
    """

    def __init__(self, frame):

        self.source_name = inspect.getframeinfo(frame).function

        # Set code start line. If the `provenance.activate` function was
        # called in the main script body, the name will be <module> and code
        # starts at line 1. If it was called inside a function (e.g. `main`),
        # we need to get the start line from the frame.
        if self.source_name == '<module>':
            self.source_lineno = 1
        else:
            self.source_lineno = inspect.getlineno(frame)

        # Get the list with all the lines of the code being tracked
        code_lines = inspect.getsourcelines(frame)[0]

        # Clean any decorators (this happens when we are tracking inside a
        # function like `main`).
        cur_line = 0
        while code_lines[cur_line].strip().startswith('@'):
            cur_line += 1
        self.start_line = cur_line

        # Store the source code lines and its AST. Source code is stored as
        # NumPy array to facilitate slicing
        source_code = code_lines[cur_line:]
        self.ast_tree = ast.parse("".join(source_code).strip())
        self.source_code = np.array(source_code)

        self._statement_lines, self._source_lines = \
            self._build_line_map(self.ast_tree, self.start_line,
                                 self.source_code)

    @staticmethod
    def _build_line_map(ast_tree, start_line, source_code):
        # This function analyzes the AST structure of the code to fetch the
        # start and end lines of each statement. A mapping of each script line
        # to the actual code is also returned, that is used later when
        # fetching the full statements.

        # We extract a stack with all nodes in the script/function body. To
        # correct the starting line if provenance is tracked inside a function
        # (e.g., `def main():`), we set a flag to use later
        is_function = False
        if (len(ast_tree.body) == 1 and
                isinstance(ast_tree.body[0], ast.FunctionDef)):
            # We are tracking inside a function
            code_nodes = ast_tree.body[0].body
            is_function = True
        else:
            # We are tracking from the script root
            code_nodes = ast_tree.body

        # Build the list with line numbers of each main node in the
        # script/function body. These are stored in `_statement_lines` array,
        # where column 0 is the starting line of the statement, and column 1
        # the end line. The line information from the AST is relative to the
        # scope of code, i.e., for code inside a function, the first line
        # after `def` is line 2. We correct this later after having the full
        # array.
        statement_lines = list()

        # We process node by node. Whenever code blocks are identified, all
        # nodes in its body are pushed to the `code_nodes` stack
        while code_nodes:
            node = code_nodes.pop(0)
            if hasattr(node, 'body'):
                # Another code block (e.g., if, for, while)
                # Just add the nodes in the body for further processing
                code_nodes.extend(node.body)

                # If `else` block is present, add it as well
                if hasattr(node, 'orelse') and node.orelse:
                    code_nodes.extend(node.orelse)

            else:
                # A statement. Find the maximum line number
                end_lines = [child.lineno for child in ast.walk(node) if
                             'lineno' in child._attributes]
                statement_lines.append((node.lineno, max(end_lines)))

        # Convert list to the final array, allowing easy masking
        statement_lines = sorted(statement_lines, key=lambda x: x[0])
        statement_lines = np.asarray(statement_lines)

        # Create an array with the line number of each line in the source code
        source_lines = np.arange(start_line,
                                 start_line + source_code.shape[0])

        # Correct the line numbers. If in a function, the `def` line is 1, and
        # the code starts on line 2 of the function body. The code in
        # `self.source_code` also starts one line before the number stored in
        # `self.start_line`.
        if is_function:
            offset = start_line - 2
            statement_lines += offset
            source_lines -= 1

        return statement_lines, source_lines

    def extract_multiline_statement(self, line_number):
        """
        Fetch all code lines in case `line_number` contains a statement that
        is the end or part of a multiline statement.

        Parameters
        ----------
        line_number : int
            Line number from :attr:`source_code`.

        Returns
        -------
        str
            The code corresponding to the full statement.
        """
        # Find the start and end line of the statement identified by
        # `line_number`
        line_diff = self._statement_lines[:, 0] - line_number
        nearest_number_index = np.argmax(line_diff[line_diff <= 0])
        statement_start, statement_end = \
            self._statement_lines[nearest_number_index, :]

        # Obtain the mask to get the source code between the start and end
        # lines
        line_mask = np.logical_and(self._source_lines >= statement_start,
                                   self._source_lines <= statement_end)

        # Retrieve the lines and join in a single string
        return "".join(
            self.source_code[line_mask]).strip()
