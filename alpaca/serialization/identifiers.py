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
def data_object_identifier(object_info):
    object_hash = object_info.hash
    type_string = object_info.type
    urn = f"{BASE_URN}:{NSS_DATA}:Python:{type_string}:{object_hash}"
    return urn


# <urn:fz-juelich.de:alpaca:file:sha256:234234324324324324234324>
def file_identifier(file_info):
    hash_type = file_info.hash_type
    file_hash = file_info.hash
    urn = f"{BASE_URN}:{NSS_FILE}:{hash_type}:{file_hash}"
    return urn


def _get_function_name(function_info):
    function_name = ""
    if function_info.module:
        function_name = f"{function_info.module}."
    function_name = f"{function_name}{function_info.name}"
    return function_name


# <urn:fz-juelich.de:alpaca:function:Python:elephant.spectral.welch_psd>
def function_identifier(function_info):
    function_name = _get_function_name(function_info)
    urn = f"{BASE_URN}:{NSS_FUNCTION}:Python:{function_name}"
    return urn


# <urn:fz-juelich.de:alpaca:script:Python:run_psd.py:f32432j34k24#4567-4567-dflsd4-dfdsfs>
def script_identifier(script_info, session_id):
    script_name = pathlib.Path(script_info.path).name
    urn = f"{BASE_URN}:{NSS_SCRIPT}:Python:{script_name}:{script_info.hash}" \
          f"#{session_id}"
    return urn


def execution_identifier(script_info, function_info, session_id, execution_id):
    function_name = _get_function_name(function_info)
    urn = f"{BASE_URN}:{NSS_EXECUTION}:Python:{script_info.hash}:" \
          f"{session_id}:{function_name}#{execution_id}"
    return urn


# Functions to extract information from identifiers, used when generating
# visualizations with NetworkX graphs.

def _strip_local_part(identifier):
    return identifier.split(f"{BASE_URN}:")[1]


def entity_info(identifier):
    local_part = _strip_local_part(identifier)
    info = local_part.split(":")

    entity_type = info[0]
    data = {'type': entity_type,
            'data_hash': info[-1]}

    if entity_type == NSS_FILE:
        data['label'] = "File"
        data['hash_type'] = info[-2]
    elif entity_type == NSS_DATA:
        data['label'] = info[-2].split(".")[-1]  # label is the class name
        data['Python_name'] = info[-2]           # store full path to class

    return data


def activity_info(identifier):
    function_name, exec_id = identifier.split(":")[-1].split("#")
    data = {
        "Python_name": function_name,
        "type": NSS_FUNCTION,
        "execution_id": exec_id
    }
    data["label"] = data["Python_name"].split(".")[-1]
    return data
