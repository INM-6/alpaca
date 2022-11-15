.. _acknowledgments:

****************************************
Acknowledgments and open source software
****************************************

The development of this open source software was funded by the `Helmholtz
School for Data Science in Life, Earth and Energy (HDS-LEE)
<http://www.hds-lee.de>`_ and  the `Human Brain Project
<http://www.humanbrainproject.eu>`_, funded from the European Union’s Horizon
2020 Framework Programme for Research and Innovation under Specific Grant
Agreements No. 785907 and No. 945539 (Human Brain Project SGA2 and SGA3).


For the graph summarization/aggregation, code from the original NetworkX
package (version 2.6) was modified. This corresponds to the functions
`ProvenanceGraph.aggregate` (modified from
`networkx.algorithms.summarization.snap_aggregation`) and
`ProvenanceGraph._snap_build_graph` (modified from
`networkx.algorithms.summarization._snap_build_graph`).

The original source code for these functions can be found at
https://github.com/networkx/networkx/blob/networkx-2.6/networkx/algorithms/summarization.py.

The NetworkX 2.6 license (3-clause BSD) can be found at
https://networkx.org/documentation/networkx-2.6/, and it is reproduced below.

License of NetworkX 2.6
-----------------------

::

    Copyright (C) 2004-2021, NetworkX Developers
    Aric Hagberg <hagberg@lanl.gov>
    Dan Schult <dschult@colgate.edu>
    Pieter Swart <swart@lanl.gov>
    All rights reserved.

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions are
    met:

      * Redistributions of source code must retain the above copyright
        notice, this list of conditions and the following disclaimer.

      * Redistributions in binary form must reproduce the above
        copyright notice, this list of conditions and the following
        disclaimer in the documentation and/or other materials provided
        with the distribution.

      * Neither the name of the NetworkX Developers nor the names of its
        contributors may be used to endorse or promote products derived
        from this software without specific prior written permission.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
    "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
    LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
    A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
    OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
    SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
    LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
    DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
    THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
    (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
    OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.