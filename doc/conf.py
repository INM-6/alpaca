# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
from datetime import date


# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------

project = 'Alpaca'
authors = 'Alpaca authors and contributors'
copyright = u"2022-{this_year}, Forschungszentrum Jülich GmbH, INM-6, IAS-6."\
    "All rights reserved.".format(this_year=date.today().year,)

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
root_dir = os.path.dirname(os.path.dirname(__file__))
with open(os.path.join(root_dir, 'alpaca', 'VERSION')) as version_file:
    # The full version, including alpha/beta/rc tags.
    release = version_file.read().strip()

# The short X.Y version.
version = '.'.join(release.split('.')[:-1])


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.doctest',
    'sphinx.ext.viewcode',
    'sphinx_tabs.tabs',
    'numpydoc',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build',
                    '**.ipynb_checkpoints',
                    'Thumbs.db',
                    '.DS_Store']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# Required to automatically create a summary page for each function listed in
# the autosummary fields of each module.
autosummary_generate = True

# Set to False to not overwrite our custom toctree/*.rst
autosummary_generate_overwrite = True


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'alabaster'

html_theme_options = {
    'font_family': 'Arial',
    'page_width': '1200px',  # default is 940
    'sidebar_width': '280px',  # default is 220
    'logo': 'images/alpaca_logo.png',
}

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
# html_favicon = 'images/*.ico'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']


# CSS file to customize and tweak display
html_css_files = [
    'css/style.css',
]


# Suppresses wrong numpy doc warnings
# see here https://github.com/phn/pytpm/issues/3#issuecomment-12133978
numpydoc_show_class_members = False

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
html_use_smartypants = True

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
html_show_sphinx = False

# If true, "(C) Copyright ..." is shown in the HTML footer. Default is True.
html_show_copyright = True

# Output file base name for HTML help builder.
htmlhelp_basename = 'alpacadoc'
