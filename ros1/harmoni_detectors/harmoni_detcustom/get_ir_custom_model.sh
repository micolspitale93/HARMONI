#!/bin/bash

echo "This script should be run from the HARMONI directory in order to place the models in a parallel directory"

mkdir -p harmoni_models/ir && cd harmoni_models/ir
gdown "https://drive.google.com/uc?id=1NOM7M36AgZjHkrO0RPA9ie1ianzy0O4c"
gdown "https://drive.google.com/uc?id=1lZP8scAAbIJetnesSr75wfOR_LByOs0c"
gdown "https://drive.google.com/uc?id=1x4JWnNQfSdV95p3iDL4nhWAYhsoL3_nE"
gdown "https://drive.google.com/uc?id=1hKZobIu1rjZyYTDXMytpNH9ZVjdwNcS-"

