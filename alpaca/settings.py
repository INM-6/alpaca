"""
For fine control of the provenance tracking with Alpaca, some settings can be
set globally.

Every time a tracked function runs, the current state of the
setting is used. The elements in the provenance records produced retain
information describing which setting value was used, when applicable.

Currently, the following settings can be defined:

* **use_content_in_file_hash**: bool
        If True, whenever a file input/output is hashed, the SHA256 hash will
        be produced. This can be slow for large files.
        If False, an alternative quicker hash (not safe to guarantee a unique
        identifier!) is implemented, based on file attributes such as path,
        timestamps, and file size.
        Default: True

* **use_builtin_hash_for_module**: list of str
        Objects from the packages defined in the list will be hashed using
        the builtin `hash` function, instead of `joblib.hash`.

        Alpaca uses the `joblib.hash` function with SHA1 algorithm to obtain
        hashes used to identify the objects. This may be problematic for some
        packages, as the objects may be subject to changes that are not useful
        to be tracked in detail.

        One example is `matplotlib.Axes` objects. `joblib.hash` is sensitive
        enough to produce a different hash every time the object is modified
        (e.g., adding a new plot, legend, etc.). For `matplotlib.Axes`
        objects, the builtin `hash` function is able to disambiguate each
        object instance among all other `matplotlib.Axes` objects within
        the script scope, but every modification will not produce a change in
        the hash value. Therefore, if adding `'matplotlib'` to the list in this
        global setting, the chain of changes in `matplotlib.Axes` objects are
        not going to be shown and the provenance track will be simplified.

        If objects of the package are elements of a container (e.g., list or
        NumPy array containing `matplotlib.Axes` objects) a special hash will
        be computed for the container, using the builtin `hash` (i.e., hash of
        the tuple containing the hashes of each element, which is obtained
        using the builtin `hash`).

        Default: []


To set/read a setting, use the function :func:`alpaca_setting`.

.. autofunction :: alpaca.alpaca_setting
"""

# Global Alpaca settings dictionary
# Should be modified only through the `alpaca_setting` function.

_ALPACA_SETTINGS = {'use_content_in_file_hash': True,
                    'use_builtin_hash_for_module': []}


def alpaca_setting(name, value=None):
    """ Gets/sets a global Alpaca setting.

    Parameters
    ----------
    name : str
        Name of the setting.
    value : Any, optional
        If not None, the setting `name` will be defined with `value`.
        If None, the current value of setting `name` will be returned.
        Default: None

    Returns
    -------
        The new value of setting `name` or its current value.

    Raises
    ------
    ValueError
        If `name` is not one of the global settings used by Alpaca or if
        the type of `value` is not compatible. Check the documentation for
        valid names and their description.
    """
    if name not in _ALPACA_SETTINGS:
        raise ValueError(f"Setting '{name}' is not valid.")

    if value is not None:
        expected_type = type(_ALPACA_SETTINGS[name])
        if type(value) is not expected_type:
            raise ValueError(f"Setting '{name}' must be '{expected_type}'")
        _ALPACA_SETTINGS[name] = value

    return _ALPACA_SETTINGS[name]