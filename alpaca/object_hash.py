"""
This module implements classes for hashing Python objects and files, that is
used by the `decorator.Provenance` class decorator to track unique objects
during the script execution.

"""

import hashlib
import inspect
import uuid
from copy import copy
from pathlib import Path
import logging

import joblib
import numpy as np
from dill._dill import save_function

from alpaca.types import ObjectInfo, FileInfo

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


class FileHash(object):
    """
    Class for hashing files.

    The SHA256 hash and file path are captured.

    The method `info` is called to obtain these provenance information as the
    `FileInfo` named tuple.

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
        self.file_path = file_path

        if use_content:
            self._hash_type = 'sha256'
            self._hash = self._get_content_file_hash(file_path)
        else:
            self._hash_type = 'attribute'
            self._hash = self._get_attribute_file_hash(file_path)

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        if isinstance(other, FileHash):
            return hash(self) == hash(other) and \
                   self._hash_type == other._hash_type
        raise TypeError("Can compare only two FileHash objects")

    def __repr__(self):
        return f"{Path(self.file_path).name}: " \
               f"[{self._hash_type}] {self._hash}"

    def info(self):
        """
        Returns provenance information for the file.

        Returns
        -------
        FileInfo
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
        return FileInfo(hash=self._hash,
                        hash_type=self._hash_type,
                        path=self.file_path)


class ObjectHasher(object):
    """
    Class for hashing Python objects, supporting memoization.

    The object hash is the SHA1 hash of its value.

    The type is a string produced by the combination of the module where it
    was defined plus the type name (both returned by :func:`type`).
    Value hash is calculated using :func:`joblib.hash` for NumPy arrays and
    other container types, or the builtin :func:`hash` function for
    matplotlib objects.

    The method `info` is called to obtain the provenance information
    associated with the object during tracking, as the `ObjectInfo` named
    tuple. The relevant metadata attributes are also stored in the tuple.

    As the same object may be hashed several times during a single analysis
    step, a builtin memoizer stores all hashes that are computed by object ID
    (according to :func:`id`).

    """

    # This is a list of object attributes that provide relevant provenance
    # information. Whether the object has one defined, it will be captured
    # together with the hash
    _metadata_attributes = ('units', 'shape', 'dtype', 't_start', 't_stop',
                            'id', 'nix_name', 'dimensionality', 'pid',
                            'create_time')

    def __init__(self):
        self._hash_memoizer = dict()

    @staticmethod
    def _get_object_package(obj):
        # Returns the string with the name of the package where the object
        # is defined (e.g., neo.core.SpikeTrain -> 'neo`)
        module = inspect.getmodule(obj)
        package = ""
        if module is not None:
            package = module.__package__.split(".")[0]
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

        # Check if the object is a NumPy array of matplotlib objects
        array_of_matplotlib = False
        if isinstance(obj, np.ndarray) and obj.dtype == np.dtype('object'):
            is_matplotlib = lambda x: self._get_object_package(x) == \
                                      'matplotlib'
            array_of_matplotlib = all(map(is_matplotlib, obj))

        if package in ['matplotlib']:
            # For matplotlib objects, we need to use the builtin hashing
            # function instead of joblib's. Multiple object hashes are
            # generated, since each time something is plotted the object
            # changes.
            object_hash = hash(obj)
        elif array_of_matplotlib:  # or isinstance(self.value, list):
            # We also have to use an exception for NumPy arrays with Axes
            # objects, as those also change when the plot changes.
            # These are usually return by the `plt.subplots()` call.
            object_hash = hash((obj_type, obj_id))
        else:
            # Other objects, like Neo, Quantity and NumPy arrays, use joblib
            object_hash = joblib.hash(obj, hash_name='sha1')

        # object_hash = hash((obj_type, value_hash))

        # Memoize the hash
        self._hash_memoizer[obj_id] = object_hash

        return object_hash

    def info(self, obj):
        """
        Returns provenance information for the object, as the `ObjectInfo`
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
        ObjectInfo
            A named tuple with the following attributes:
            * hash : int
                Hash of the object.
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
            return ObjectInfo(hash=unique_id, type=obj_type, id=obj_id,
                              details={})

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
        obj_hash = self._get_object_hash(obj=obj, obj_type=obj_type,
                                         obj_id=obj_id, package=package)

        return ObjectInfo(hash=obj_hash, type=obj_type, id=obj_id,
                          details=details)
