#!/bin/bash

PROFILE=$1

. ./setenv.sh $PROFILE

source ${APP_PYENV}/bin/activate

python3 -u main.py