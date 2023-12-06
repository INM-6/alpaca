=============
Release Notes
=============

Release 0.2.0
*************

New functionality and features
------------------------------
* Added functionality to capture and serialize object values (e.g., values of integers, booleans, floats, complex numbers, NumPy numeric objects, or any other object type defined by the user) (#27).
* Added support for adding semantic annotations in the captured provenance using ontologies (#26).
* Added option to select levels captured in nested container outputs (#10, #25).
* Extended attribute selection for graph aggregation (#24).
* Improved logging and progress bar output (#14).
* Improved performance when generating the provenance graph (#13).
* Optimize attribute selection for graph visualization (#16).
* Added ability to merge multiple provenance sources into a single visualization graph (#22).
* Implemented functionality to add a suffix to the base file name in `get_file_name` utility function (#21).
* Improved tracking of Python objects (#20).

Bug fixes
---------
* Fixed error when tracking provenance of static methods in objects (#23).
* Added support to other form of comprehensions (e.g., dictionaries, sets) as functions executed inside comprehensions other than list were not tracked (#19).
* Fixed error when getting the module version when tracking a method descriptor (#17).
* Added option to not store the list of members (i.e., all nodes that were aggregated in a super node) during graph aggregation, as in large graphs this resulted in an error when loading the graph in Gephi (#15).
* Added support to track functions called as an attribute of a module (i.e., in the form `module.function(input)`), as they were not tracked by the decorator (#12).
* Changed `save_provenance` function to avoid error when not capturing provenance (e.g., when the provenance capture was deactivated and the function called at the end of the script) (#11).

Release 0.1.0
*************

This release constitutes the initial Alpaca release.
