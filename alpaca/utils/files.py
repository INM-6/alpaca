"""
This module contains utility functions to generate or get information
from file names.
"""

from pathlib import Path


def get_file_name(source, output_dir=None, extension=None):
    """
    Function that generates a file name with extension `extension` and the
    same base name as in `source`. The full path is based on `output_dir` if
    specified. Otherwise, it will be the same path as `source`. User and
    relative paths are expanded.

    Parameters
    ----------
    source : str or Path-like
        Source path or file name to generate the new file name. The base name
        will be considered.
    output_dir : str, optional
        If not None, the generated file name will have this path.
        Default: None
    extension : str, optional
        If not None, the extension of the generated file name will be changed
        to `extension`. If None, the same extension as `source` will be used.
        The extension may start with period.

    Returns
    -------
    str
        File name, according to the parameters selected. If both `output_dir`
        and `extension` are None, the result will be equal to `source`. The
        result path is absolute, with user and relative paths expanded.
    """
    if not isinstance(source, Path):
        source = Path(source)

    if extension is not None:
        if not extension.startswith("."):
            extension = "." + extension
        base_name = source.with_suffix(extension)
    else:
        base_name = source

    if output_dir is not None:
        base_name = Path(output_dir) / base_name.name
    return str(base_name.expanduser().resolve().absolute())


def _get_prov_file_format(file_name):
    # Returns a string describing the file format based on the extension in
    # `file_name`. `.rdf` files are described as XML, `.ttl` files are
    # described as Turtle, and `.json` are described as JSON-LD. Other
    # extensions are returned as provided. The return value is compatible with
    # RDFLib serialization format strings. Returns None if no extension.

    file_location = Path(file_name)

    extension = file_location.suffix
    if not extension.startswith('.'):
        return None
    file_format = extension[1:]

    file_format_map = {
        'ttl': 'turtle',
        'rdf': 'xml',
        'json': 'json-ld',
    }

    if file_format in file_format_map:
        return file_format_map[file_format]

    return file_format
