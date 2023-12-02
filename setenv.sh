#!/bin/bash

PROFILE=$1

if [  -z "$PROFILE" ]; then
  PROFILE=dev
fi


if [ "$PROFILE" = "dev" ]; then
  echo "setting environment for profile dev"
  export APP_HOME=$(pwd)
  export APP_CONFIG=${APP_HOME}/config
  export APP_PYENV=${PYENV}/qgen-api
  . .secrets
fi

if [ "$PROFILE" = "prod" ]; then
  echo "setting environment for profile prod"
  export APP_ENV=prod
fi