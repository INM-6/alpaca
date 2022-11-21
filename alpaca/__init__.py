"""
Alpaca is a package for easy provenance capture during the execution of
analysis workflows based on Python scripts and Jupyter notebooks.

"""

from .decorator import (Provenance, activate, deactivate, save_provenance,
                        print_history)
from .serialization import AlpacaProvDocument
from .graph import ProvenanceGraph
from .ipython import activate_ipython, deactivate_ipython
from .settings import alpaca_setting
from .utils import files
