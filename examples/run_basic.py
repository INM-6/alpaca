"""
Example showing the basic usage for provenance tracking using Alpaca.
This example is based on the publicly available Reach2Grasp dataset, that
must be downloaded from the repository together with the supporting code.
Details for setting the environment can be found in the documentation.

The session file to be used is passed as a parameter when running the script:

    run_basic.py [path_to_file.nsX]

This scripts uses the Elephant toolbox for analysis (www.python-elephant.org).
"""

import os
import sys

import numpy as np
import logging

from reachgraspio import ReachGraspIO
from elephant.statistics import isi, mean_firing_rate

from alpaca import Provenance, activate, save_provenance
from alpaca.utils.files import get_file_name
import neo

# Set the logging up, if desired
# With DEBUG, helpful messages will be displayed during tracking

logging.basicConfig(level=logging.INFO)

# We need to apply the decorator to functions from other modules
# A list with the name of the function arguments that are inputs must be
# provided to the decorator constructor through the `inputs` argument.
# The names in the list are according to the function definition.

isi = Provenance(inputs=['spiketrain'])(isi)
mean_firing_rate = Provenance(inputs=['spiketrain'])(mean_firing_rate)

# The `np.array` function does not have named arguments. Therefore, the
# `inputs` argument to the constructor is the integer that corresponds to the
# input argument order.

np.array = Provenance(inputs=[0])(np.array)


# User-defined functions in the script can be decorated using the @ syntax
# If a function has arguments that define input or output files, their names
# can be passed using the `file_input` or `file_output` arguments to the
# decorator constructor, respectively. For `inputs`, a list must always be
# passed. If no arguments are data inputs, then pass an empty list.

@Provenance(inputs=[], file_input=['session_filename'])
def load_data(session_filename):
    """
    Loads Reach2Grasp data using the custom BlackRockIO object ReachGraspIO.

    Parameters
    ----------
    session_filename : str
        Full path to the dataset file.

    Returns
    -------
    neo.Block
        Block container with the session data.

    """
    file, ext = os.path.splitext(session_filename)
    file_path = os.path.dirname(session_filename)

    session = ReachGraspIO(file, odml_directory=file_path,
                           verbose=False)

    block = session.read_block(load_waveforms=False, nsx_to_load=None,
                               load_events=True, lazy=False, channels=[10],
                               units='all')

    return block


def main(session_filename):
    activate()

    # Load the data
    block = load_data(session_filename)

    # Compute some statistics using the first spiketrain in the segment
    isi_times = isi(block.segments[0].spiketrains[0], axis=0)
    firing_rate = mean_firing_rate(block.segments[0].spiketrains[0])

    isi_times = isi(block.segments[0].spiketrains[1], axis=0)

    # Generate an array representing artificial spike times and compute
    # statistics
    generated_spike_times = np.array([0.001, 0.202, 0.405, 0.607, 0.904, 1.1])
    isi_times = isi(generated_spike_times)
    firing_rate = mean_firing_rate(generated_spike_times)

    # Save the provenance as PROV, with optional plotting
    prov_file_format = "ttl"
    prov_file = get_file_name(__file__, extension=prov_file_format)

    save_provenance(prov_file, file_format=prov_file_format, plot=True,
                    show_element_attributes=False)


if __name__ == "__main__":

    if len(sys.argv) < 2:
        raise ValueError("You must specify the path to the data set file.")

    main(sys.argv[1])
