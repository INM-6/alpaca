"""
This module contains utility functions to work with file names and extensions.

.. autofunction:: alpaca.utils.get_file_name

"""

from pathlib import Path


RDF_FILE_FORMAT_MAP = {
    'ttl': 'turtle',
    'rdf': 'xml',
    'json': 'json-ld',
}


def get_file_name(source, output_dir=None, extension=None, suffix=None):
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
        Default: None
    suffix : str, optional
        If not None, this will be added as a suffix to the base name of
        `source`, before the extension.
        Default: None

    Returns
    -------
    str
        File name, according to the parameters selected. If both `output_dir`
        and `extension` are None, the result will be equal to `source`. The
        result path is absolute, with user and relative paths expanded.
    """
    if not isinstance(source, Path):
        source = Path(source)

    if suffix is not None:
        parent, name, ext = source.parent, source.stem, source.suffix
        name = f"{name}{suffix}"
        source = (parent / name).with_suffix(ext)

    if extension is not None:
        if not extension.startswith("."):
            extension = f".{extension}"
        base_name = source.with_suffix(extension)
    else:
        base_name = source

    if output_dir is not None:
        base_name = Path(output_dir) / base_name.name
    return str(base_name.expanduser().resolve().absolute())


def _get_file_format(file_name):
    # Returns a string describing the file format based on the extension in
    # `file_name`. Returns None if no extension.
    file_location = Path(file_name)

    extension = file_location.suffix
    if not extension.startswith('.'):
        return None
    file_format = extension[1:]

    return file_format


def _get_prov_file_format(file_name):
    # Returns a string describing the file format based on the extension in
    # `file_name`. `.rdf` files are described as XML, `.ttl` files are
    # described as Turtle, and `.json` are described as JSON-LD. Other
    # extensions are returned as provided. The return value is compatible with
    # RDFLib serialization format strings. Returns None if no extension.

    file_format = _get_file_format(file_name)

    if file_format and file_format in RDF_FILE_FORMAT_MAP:
        return RDF_FILE_FORMAT_MAP[file_format]

    return file_format
