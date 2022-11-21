"""
This module implements classes for getting the relevance provenance
information from Python objects and files (e.g., hashes and metadata).
They are used by the `decorator.Provenance` class decorator to track unique
objects during the script execution, and also to represent the objects in the
PROV files generated with the Alpaca model (identifiers).

The classes defined in this module are not intended to be used directly by
the user, but are used internally by the `decorator.Provenance` decorator.
"""

import hashlib
import inspect
import uuid
from copy import copy
from pathlib import Path
import logging
from collections.abc import Iterable

import joblib
import numpy as np
from dill._dill import save_function

from alpaca.types import DataObject, File

# Need to use `dill` pickling function to support lambdas.
# Some objects may have attributes that are lambdas. One example is the
# test case of Nose. If the unit test accesses variables in the TestCase class
# (e.g., `self.spiketrains`), the hashing of the `self` object fails.
# Here we update the dispatch table of the `joblib.Hasher` object to use
# the function from `dill` that supports these lambda attributes.
joblib.hashing.Hasher.dispatch[type(save_function)] = save_function


# Create logger and set configuration
logger = logging.getLogger(__file__)
log_handler = logging.StreamHandler()
log_handler.setFormatter(logging.Formatter("[%(asctime)s] alpaca.hash -"
                                           " %(levelname)s: %(message)s"))
logger.addHandler(log_handler)
logger.propagate = False


class _FileInformation(object):
    """
    Class for getting information from files.

    The SHA256 hash and file path are captured.

    The method `info` is called to obtain these provenance information as the
    `File` named tuple.

    Easy comparison between files can be done using the equality operator.

    Parameters
    ----------
    file_path : str or path-like
        The path to the file that is being hashed.
    use_content: bool, optional
        If True, the file content will be used and a SHA256 hash will be
        computed. If False, a hash based on file attributes (file path and
        timestamps) will be computed.
        Default: True
    """

    # TODO: quick hashing based on file path and timestamps
    @staticmethod
    def _get_attribute_file_hash(file_path):
        return 0

    @staticmethod
    def _get_content_file_hash(file_path, block_size=4096 * 1024):
        file_hash = hashlib.sha256()

        with open(file_path, 'rb') as file:
            for block in iter(lambda: file.read(block_size), b""):
                file_hash.update(block)

        return file_hash.hexdigest()

    def __init__(self, file_path, use_content=True):
        self.file_path = Path(file_path).expanduser().absolute()

        if use_content:
            self._hash_type = 'sha256'
            self._hash = self._get_content_file_hash(self.file_path)
        else:
            self._hash_type = 'attribute'
            self._hash = self._get_attribute_file_hash(self.file_path)

    def __eq__(self, other):
        if isinstance(other, _FileInformation):
            return self._hash == other._hash and \
                   self._hash_type == other._hash_type
        raise TypeError("Can compare only two `_FileInformation` objects")

    def __repr__(self):
        return f"{self.file_path.name}: " \
               f"[{self._hash_type}] {self._hash}"

    def info(self):
        """
        Returns provenance information for the file.

        Returns
        -------
        types.File
            A named tuple with the following attributes:
            * hash : int
                Hash of the file. If hashing is done using the content, this
                is the SHA256 hash. Otherwise, it is a hash based on the
                attributes of the file (file path and timestamps).
            * hash_type: {'sha256', 'attribute'}
                String storing the hash type.
            * path : str or path-like
                The path to the file that was hashed.
        """
        return File(hash=self._hash,
                    hash_type=self._hash_type,
                    path=self.file_path)


class _ObjectInformation(object):
    """
    Class for hashing Python objects and getting their information, supporting
    memoization.

    The object hash is the SHA1 hash of its value.

    The type is a string produced by the combination of the module where it
    was defined plus the type name (both returned by :func:`type`).

    Value hash is calculated using :func:`joblib.hash` or the builtin
    :func:`hash` function, depending on the `use_builtin_hash` parameter set
    during initialization.

    The method `info` is called to obtain the provenance information
    associated with the object during tracking, as the `DataObject` named
    tuple. The relevant metadata attributes are also stored in the tuple.

    As the same object may be hashed several times during a single analysis
    step, a builtin memoizer stores all hashes that are computed by object ID
    (according to :func:`id`).

    Parameters
    ----------
    use_builtin_hash : list, optional
        List of package names whose object hashes will be computed using the
        Python builtin `hash` function, instead of `joblib.hash` function.
        Default: None
    """

    # This is a list of object attributes that provide relevant provenance
    # information. Whether the object has one defined, it will be captured.
    _metadata_attributes = ('units', 'shape', 'dtype', 't_start', 't_stop',
                            'id', 'nix_name', 'dimensionality', 'pid',
                            'create_time')

    def __init__(self, use_builtin_hash=None):
        self._hash_memoizer = dict()
        self._use_builtin_hash = copy(use_builtin_hash) \
            if use_builtin_hash is not None else []

    @staticmethod
    def _get_object_package(obj):
        # Returns the string with the name of the package where the object
        # is defined (e.g., neo.core.SpikeTrain -> 'neo')
        module = inspect.getmodule(obj)
        package = ""
        if module is not None:
            package = module.__name__.split(".")[0]
        return package

    def _get_object_hash(self, obj, obj_type, obj_id, package):
        # Computes the hash for `obj`. `obj_type` and `package` are the
        # string representations of the type and package, and `obj_id` the
        # `id()` of the object

        logger.debug(f"{obj_type}, id={obj_id}")

        # If we already computed the hash for the object during this function
        # call, retrieve it from the memoized values
        if obj_id in self._hash_memoizer:
            return self._hash_memoizer[obj_id]

        logger.debug("Hashing")

        hash_method = None
        if package in self._use_builtin_hash:
            # Use the builtin hashing function instead of joblib's. This avoids
            # the case where object changes result in multiple object hashes,
            # which will produce a complex provenance track
            object_hash = hash(obj)
            hash_method = "Python"
        else:
            # Check if the object is a container of objects that should be
            # hashed with the Python builtin function. For NumPy arrays, we
            # restrict this to arrays of dtype=object, as they are the ones
            # that can contain objects
            container_builtin_hash = False
            if isinstance(obj, Iterable) and not (
                isinstance(obj, np.ndarray) and obj.dtype != object):

                iterator = obj if not isinstance(obj, np.ndarray) \
                    else obj.ravel()

                # Loop over elements. If any element is not from the requested
                # packages, abort the loop
                container_builtin_hash = True
                for element in iterator:
                    container_builtin_hash = \
                        container_builtin_hash and \
                        (self._get_object_package(element) in
                         self._use_builtin_hash)

                    if not container_builtin_hash:
                        break

            if container_builtin_hash:
                # We also have to use the builtin hash if objects from the
                # requested packages are stored in containers (e.g., NumPy
                # arrays with matplotlib Axes objects).

                iterator = obj if not isinstance(obj, np.ndarray) \
                    else obj.ravel()
                object_hash = joblib.hash(
                    tuple([hash(element) for element in iterator]),
                    hash_name='sha1'
                )
                hash_method = "Python"
            else:
                # Other objects, like Neo, Quantity and NumPy arrays, use
                # joblib's hash function
                object_hash = joblib.hash(obj, hash_name='sha1')
                hash_method = "joblib"

        # Memoize the hash
        self._hash_memoizer[obj_id] = (object_hash, hash_method)

        return object_hash, hash_method

    def info(self, obj):
        """
        Returns provenance information for the object, as the `DataObject`
        named tuple.

        Metadata (e.g., annotations in Neo objects) is also captured. Any
        relevant attributes are also captured as metadata.

        If the object is None, then the hash is replaced by a unique id for
        the object.

        Parameters
        ----------
        obj : object
            Python object to get the provenance information.

        Returns
        -------
        types.DataObject
            A named tuple with the following attributes:
            * hash : int
                Hash of the object.
            * hash_method : {"Python", "joblib", "None"}
                Hash function used in the computation. If the
                :attr:`use_builtin_hash` list is defined, the builtin Python
                hash function is used for objects of the packages in the list.
                For None objects, the value will be "None".
            * type: str
                Type of the object.
            * id : int
                Reference for the object.
            * details : dict
                Extended information (metadata) on the object.
        """
        type_information = type(obj)
        obj_type = f"{type_information.__module__}.{type_information.__name__}"
        obj_id = id(obj)

        # All Nones will have the same hash. Use UUID instead
        if obj is None:
            unique_id = uuid.uuid4()
            return DataObject(hash=unique_id, hash_method="None",
                              type=obj_type, id=obj_id, details={})

        # Here we can extract specific metadata to record
        details = {}

        # Currently fetching the whole instance dictionary
        if hasattr(obj, '__dict__'):
            # Need to copy otherwise the hashes change
            details = copy(obj.__dict__)

        # Store specific attributes that are relevant for arrays, quantities
        # Neo objects, and AnalysisObjects
        for attr in self._metadata_attributes:
            if hasattr(obj, attr):
                details[attr] = getattr(obj, attr)

        # Compute object hash
        package = self._get_object_package(obj)
        obj_hash, hash_method = self._get_object_hash(obj=obj,
                                         obj_type=obj_type,
                                         obj_id=obj_id, package=package)

        return DataObject(hash=obj_hash, hash_method=hash_method,
                          type=obj_type, id=obj_id, details=details)
