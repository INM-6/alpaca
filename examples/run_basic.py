"""
Example showing the basic usage for provenance tracking using Alpaca.
This example is based on the publicly available Reach2Grasp dataset (in NIX
format) that must be downloaded from the repository. The details for setting
the environment can be found in the documentation.

The session file to be used is passed as a parameter when running the script:

    run_basic.py [path_to_file.nix]

This scripts uses the Elephant toolbox for analysis (www.python-elephant.org).

It produces the interspike interval (ISI) histogram of the first spiketrain in
the dataset.

This script is the basis for the "Simple example" page in the Examples section
of the documentation.
"""

import sys
from pathlib import Path
import logging

import numpy as np
import matplotlib.pyplot as plt

import quantities as pq
import neo

from elephant.statistics import isi

from alpaca import Provenance, activate, save_provenance
from alpaca.utils import get_file_name


# Set the logging up, if desired
# With DEBUG, helpful messages will be displayed during tracking

logging.basicConfig(level=logging.INFO)


# We need to apply the decorator to functions from other modules
# A list with the name of the function arguments that are inputs must be
# provided to the decorator constructor through the `inputs` argument.
# The names in the list are according to the function definition.

isi = Provenance(inputs=['spiketrain'])(isi)


# User-defined functions in the script can be decorated using the @ syntax
# If a function has arguments that define input or output files, their names
# can be passed using the `file_input` or `file_output` arguments to the
# decorator constructor, respectively. For `inputs`, a list must always be
# passed. If no arguments are data inputs, then pass an empty list.

@Provenance(inputs=[], file_input=['session_filename'])
def load_data(session_filename):
    path = Path(session_filename).expanduser().absolute()
    session = neo.NixIO(str(path))
    block = session.read_block()
    return block


@Provenance(inputs=['isi_times'])
def isi_histogram(isi_times, bin_size=2*pq.ms, max_time=500*pq.ms):
    upper_bound = max_time.rescale(bin_size.units).magnitude.item()
    step = bin_size.magnitude.item()
    edges = np.arange(0, upper_bound, step)

    if isinstance(isi_times, pq.Quantity):
        times = isi_times.rescale(bin_size.units).magnitude
    elif isinstance(isi_times, np.ndarray):
        times = isi_times
    else:
        raise TypeError("ISI is not `pq.Quantity` or `np.ndarray`!")

    counts, edges = np.histogram(times, bins=edges)
    return counts, (edges * bin_size.units)


@Provenance(inputs=['counts', 'edges'], file_output=['plot_file'])
def plot_isi_histogram(plot_file, counts, edges, title=None):
    fig, ax = plt.subplots()
    bar_widths = np.diff(edges)
    ax.bar(edges[:-1].magnitude, height=counts, align='edge', width=bar_widths)
    ax.set_xlabel(f"Inter-spike interval ({edges.dimensionality.string})")
    ax.set_ylabel("Count")
    if title is not None:
        ax.set_title(title)
    fig.savefig(plot_file)


def main(session_filename):
    activate()

    # Load the data
    block = load_data(session_filename)

    # Compute the ISI of the first spiketrain in the segment
    spiketrains = block.segments[0].spiketrains
    for st in spiketrains:
    isi_times = isi([spiketrains[0])

    unit_name = spiketrains[0].name

    # Compute the histogram of the ISIs
    isi_counts, isi_edges = isi_histogram(isi_times)

    # Plot the histogram
    plot_isi_histogram("isi_plot.png", isi_counts, isi_edges,
                       title=f"Unit: {unit_name}")

    # Save the provenance as PROV
    prov_file = get_file_name(__file__, extension='ttl')
    save_provenance(prov_file)


if __name__ == "__main__":

    if len(sys.argv) < 2:
        raise ValueError("You must specify the path to the data set file.")

    main(sys.argv[1])
