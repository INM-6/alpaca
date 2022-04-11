"""
This module contains utility functions to generate file names.

"""

from pathlib import Path


def get_file_name(source, output_dir=None, extension=None):
    """
    Function that generates a file name with extension `extension` and the
    same base name as in `source`. The full path is based on `output_dir`.

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
        and `extension` are None, the result will be equal to `source`.
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
        base_name = Path(output_dir).with_name(base_name.name)
    return str(base_name)


def _get_prov_file_format(file_name):
    file_location = Path(file_name)

    extension = file_location.suffix
    if not extension.startswith('.'):
        raise ValueError("File has no extension. No format can be inferred")
    file_format = extension[1:]

    if file_format == 'ttl':
        file_format = 'rdf'

    return file_format
