#!/bin/bash

#docker pull harmoniteam/harmoni:kinetic-base

#docker pull harmoniteam/harmoni:kinetic-full

#docker pull harmoniteam/harmoni:kinetic-face_detect

#docker pull harmoniteam/harmoni:noetic-base

docker push harmoni02/harmoni2.0:full

docker push harmoni02/harmoni2.0:detectors

docker push harmoni02/harmoni2.0:imageai

docker push harmoni02/harmoni2.0:fer

docker push harmoni02/harmoni2.0:face_detect