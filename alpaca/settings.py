"""
For fine control of the provenance tracking with Alpaca, some settings can be
set globally.

Every time a tracked function runs, the current state of the
setting is used. The elements in the provenance records produced retain
information describing which setting value was used, when applicable.

Currently, the following settings can be defined:

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

* **authority**: str
        The string defining the authority component used in the identifiers
        throughout Alpaca.

        Data objects, files, scripts, functions, and function executions are
        serialized to RDF using URN identifiers. The basic form of the
        identifier string is `urn:[authority]:alpaca:[complement]`, where
        `[complement]` is a string composed by specific information of each
        element identified.

        `[authority]` is a string that points to the institute or organisation
        which has responsibility over the script execution, and is defined
        by this setting.

        Default: "my-authority"

* **store_values**: list of str
        The values of the objects from the types in the list will be stored
        together with the provenance information. Note that objects of the
        builtin types `str`, `bool`, `int`, `float` and `complex`, as well as
        the NumPy numeric types (e.g. `numpy.float64`) are stored by default.
        This option should be used to store values of more complex types, such
        as dictionaries. In this case, the list in this setting should have
        the `builtins.dict` entry. The strings are the full path to the Python
        object, i.e., `[module].[...].[object_class]`.


To set/read a setting, use the function :func:`alpaca_setting`.

.. autofunction :: alpaca.alpaca_setting
"""

# Global Alpaca settings dictionary
# Should be modified only through the `alpaca_setting` function.

_ALPACA_SETTINGS = {'use_builtin_hash_for_module': [],
                    'authority': "my-authority",
                    'store_values': []}


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
