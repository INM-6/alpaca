"""
This module implements functions to activate provenance capture when using
IPython (e.g., when running Jupyter Notebooks).
"""

PROV_LINE = "alpaca.activate()\n"


def _add_provenance_to_cell(lines):
    # A cell transformer function, that is executed before the cell code is
    # run. It adds the provenance activate function to the first line of the
    # code. This ensures that the frame of that cell will be tracked.

    if lines:
        if lines[0] != PROV_LINE:
            return [PROV_LINE] + lines
    return lines


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
