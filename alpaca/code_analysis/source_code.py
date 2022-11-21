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
    source_code_lines : np.ndarray
        Lines of the code from `frame`.
    """

    def __init__(self, frame):

        # Get the name of the function where activate was called
        self.source_name = inspect.getframeinfo(frame).function

        # Get current line in the frame
        exec_line = inspect.getlineno(frame)

        # Get the list with all the lines of the code being tracked
        code_lines = inspect.getsourcelines(frame)[0]

        # Clean any decorators (this happens when we are tracking inside a
        # function like `main`). The AST parser cannot deal with them.
        cur_line = 0
        while code_lines[cur_line].strip().startswith('@'):
            cur_line += 1
        parsed_lines = code_lines[cur_line:]

        # Parse and store the source code AST
        self.ast_tree = ast.parse("".join(parsed_lines).strip())

        # Set code start line. If the `provenance.activate` function was
        # called in the main script body, the name will be <module> and code
        # starts at line 1. If it was called inside a function (e.g. `main`),
        # we need to get the start line from the frame. In this case, the line
        # number is the position where the activate function was called
        if self.source_name == '<module>':
            self.source_lineno = 1
        else:
            activate_line = self._find_activate_line(self.ast_tree,
                                                     self.source_name)
            self.source_lineno = exec_line - (activate_line - 1)

        # Store the actual source lines. NumPy array is used to facilitate
        # slicing with masks
        self.source_code_lines = np.array(parsed_lines)

        # Build the mapping arrays, to fetch the statements later
        self._statement_lines, self._source_lines = \
            self._build_line_map(self.ast_tree, self.source_lineno,
                                 self.source_code_lines)

    @staticmethod
    def _find_activate_line(full_ast, function_name):
        # This function creates an AST and finds the location of the function
        # `activate` function call statement. We need this to find the correct
        # the position in the source code list

        if isinstance(full_ast.body[0], ast.FunctionDef):

            function_def = full_ast.body[0]

            if function_def.name == function_name:

                for statement in function_def.body:
                    for node in ast.walk(statement):
                        if ((isinstance(node, ast.Call)) and
                                (node.func.id in ('activate',))):
                            return statement.lineno
        return 0

    @staticmethod
    def _build_line_map(ast_tree, start_line_number, source_code_lines):
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
        # script/function body. These are stored in `statement_lines_numbers`
        # array, where column 0 is the starting line of the statement, and
        # column 1 the end line. The line information from the AST is relative
        # to the scope of code, i.e., for code inside a function, the first
        # line of the `def` statement is line 1. We correct this later after
        # having the full array.
        statement_lines_numbers = list()

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
                statement_lines_numbers.append((node.lineno, max(end_lines)))

        # Convert list to the final array, allowing easy masking
        statement_lines_numbers = sorted(statement_lines_numbers,
                                         key=lambda x: x[0])
        statement_lines_numbers = np.asarray(statement_lines_numbers)

        # Correct line numbers if source code is from function
        # In the end, `statement_lines_numbers` ranges are with respect to
        # the actual line numbers in the script, for each statement.

        if is_function:
            statement_lines_numbers += (start_line_number - 1)

        # Create an array with the line number of each line in
        # `source_code_lines` array. This will be used for masking
        source_lines_numbers = np.arange(
            start_line_number, start_line_number + source_code_lines.shape[0])

        return statement_lines_numbers, source_lines_numbers

    def extract_multiline_statement(self, line_number):
        """
        Fetch all code lines in case `line_number` contains a statement that
        is the end or part of a multiline statement.

        Parameters
        ----------
        line_number : int
            Line number from :attr:`source_code_lines`.

        Returns
        -------
        str or None
            The code corresponding to the full statement, or None if no
            statement was found in that line.
        """
        # Find the start and end line of the statement identified by
        # `line_number`
        line_diff = self._statement_lines[:, 0] - line_number
        nearest_mask = line_diff <= 0

        if not np.any(nearest_mask):
            return None

        nearest_number_index = np.argmax(line_diff[nearest_mask])
        statement_start, statement_end = \
            self._statement_lines[nearest_number_index, :]

        if line_number > statement_end:
            return None

        # Obtain the mask to get the source code between the start and end
        # lines
        line_mask = np.logical_and(self._source_lines >= statement_start,
                                   self._source_lines <= statement_end)

        # Retrieve the lines and join in a single string
        lines = self.source_code_lines[line_mask]
        statement = "".join(lines).strip()
        return statement
