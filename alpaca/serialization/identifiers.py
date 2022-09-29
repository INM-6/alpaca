"""
This module generate URN identifiers for the identification of objects within
Alpaca.
"""

import pathlib

# Values that are used to compose the URNs
# URNs take the general form "urn:NID:NSS", followed by optional components
# according to RFC 8141.

AUTHORITY = "fz-juelich.de"

NID_ALPACA = f"{AUTHORITY}:alpaca"

NSS_FUNCTION = "function"             # Functions executed
NSS_FILE = "file"                     # Files accessed
NSS_DATA = "object"                   # Data objects (input/outputs/containers)
NSS_SCRIPT = "script"                 # The execution script
NSS_EXECUTION = "function_execution"  # Execution of a function

BASE_URN = f"urn:{NID_ALPACA}"


# <urn:fz-juelich.de:alpaca:object:Python:neo.core.AnalogSignal:423423432432423432432>
def data_object_identifier(info):
    object_hash = info.hash
    type_string = info.type
    urn = f"{BASE_URN}:{NSS_DATA}:Python:{type_string}:{object_hash}"
    return urn


# <urn:fz-juelich.de:alpaca:file:sha256:234234324324324324234324>
def file_identifier(info):
    hash_type = info.hash_type
    file_hash = info.hash
    urn = f"{BASE_URN}:{NSS_FILE}:{hash_type}:{file_hash}"
    return urn


# <urn:fz-juelich.de:alpaca:function:Python:elephant.spectral.welch_psd>
def function_identifier(info):
    function_name = ""
    if info.module:
        function_name = f"{info.module}."
    function_name = f"{function_name}{info.name}"

    urn = f"{BASE_URN}:{NSS_FUNCTION}:Python:{function_name}"
    return urn


# <urn:fz-juelich.de:alpaca:script:Python:run_psd.py:f32432j34k24#4567-4567-dflsd4-dfdsfs>
def script_identifier(info, session_id):
    script_name = pathlib.Path(info.path).name
    urn = f"{BASE_URN}:{NSS_SCRIPT}:Python:{script_name}:{info.hash}" \
          f"#{session_id}"
    return urn


def execution_identifier(info, session_id, execution_id):
    urn = f"{BASE_URN}:{NSS_EXECUTION}:Python:{info.hash}:{session_id}" \
          f"#{execution_id}"
    return urn
