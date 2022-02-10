"""
This module implements functions to activate provenance capture when using
IPython (e.g., when running Jupyter Notebooks).

"""

PROV_LINE = "alpaca.activate()\n"


def _add_provenance_to_cell(lines):
    if lines:
        if lines[0] != PROV_LINE:
            return [PROV_LINE] + lines
    return lines


def activate_ipython():
    """
    Activates Alpaca provenance tracking when using IPython.

    This should be executed before any other cells that must be tracked are
    executed.
    """
    try:
        ip = get_ipython()
        ip.input_transformers_cleanup.append(_add_provenance_to_cell)
    except NameError:
        print("You are running outside IPython. 'alpaca.activate()' should"
              "be used.")
