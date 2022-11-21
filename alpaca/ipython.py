"""
This module implements functions to activate provenance capture when using
IPython (e.g., when running Jupyter Notebooks).
"""
import inspect
from alpaca import Provenance

PROV_LINES = ["from alpaca.ipython import _set_ipython_frame\n",
              "_set_ipython_frame()\n"]


def _add_provenance_to_cell(lines):
    # A cell transformer function, that is executed before the cell code is
    # run. It adds the provenance activate function to the first line of the
    # code. This ensures that the frame of that cell will be tracked.

    if lines:
        if lines[0:2] != PROV_LINES:
            return PROV_LINES + lines
    return lines


def _set_ipython_frame():
    # Hidden activate function. This is similar to `alpaca.activate()`.
    Provenance._set_calling_frame_ipython(inspect.currentframe().f_back)
    Provenance.active = True


def activate_ipython():
    """
    Activates Alpaca provenance tracking when using IPython (e.g., in Jupyter
    notebooks).

    This function should be used instead of the :func:`activate` for scripts.
    It should be executed before any other cells that must be tracked are
    executed.

    Raises
    ------
    NameError
        If calling outside a Jupyter notebook (e.g., script).

    Examples
    --------
    It is recommended to put in the first cell, after importing
    from Alpaca.

    >>> from alpaca import activate_ipython
    >>> activate_ipython()

    """
    try:
        ip = get_ipython()
        ip.input_transformers_cleanup.append(_add_provenance_to_cell)
    except NameError:
        print("You are running outside IPython. 'alpaca.activate()' should"
              "be used.")


def deactivate_ipython():
    """
    Deactivates Alpaca provenance tracking when using IPython.
    """
    try:
        # Remove the cell transformer that adds the activation code
        ip = get_ipython()
        for index, transformer in enumerate(ip.input_transformers_cleanup):
            if transformer == _add_provenance_to_cell:
                ip.input_transformers_cleanup.pop(index)
                break

        # Deactivate decorator
        Provenance.active = False

    except NameError:
        print("You are running outside IPython. 'alpaca.activate()' should"
              "be used.")
