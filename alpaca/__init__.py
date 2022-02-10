"""
Alpaca is a package for easy provenance capture during the execution of
analysis workflows based on Python scripts and Jupyter notebooks.

"""

from .decorator import (Provenance, activate, deactivate, save_provenance,
                        print_history)

from .ipython import activate_ipython
from .utils import files
