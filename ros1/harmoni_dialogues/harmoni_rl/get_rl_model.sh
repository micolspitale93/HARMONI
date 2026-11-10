#!/bin/bash

echo "This script should be run from the HARMONI directory in order to place the models in a parallel directory"

mkdir -p harmoni_models/rl && cd harmoni_models/rl
gdown "https://drive.google.com/uc?id=1GMyNOSftI6unKaiuxDX2QKxUZe6QykLd"
gdown "https://drive.google.com/uc?id=12IMyMlJFwLeSvyVMJfZ1mCB5QlJxddIM"
gdown "https://drive.google.com/uc?id=1NWelQyH537ZyqOaAHkcgzmHhNpyUYWHZ"