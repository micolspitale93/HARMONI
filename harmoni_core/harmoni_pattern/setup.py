# ! DO NOT MANUALLY INVOKE THIS setup.py, USE CATKIN INSTEAD

from distutils.core import setup
from catkin_pkg.python_setup import generate_distutils_setup

# fetch values from package.xml
setup_args = generate_distutils_setup(
     scripts=[''],
     packages=['harmoni_pattern'],
     package_dir={'': 'src'}, #node eventually
)

setup(**setup_args)
