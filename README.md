docker run -d -p 17985:7979 \
    --name qgen-api \
    --gpus device=0 \
    -e APP_HOME=/zn/app \
    -e APP_CONFIG=/zn/app/config \
    -e APP_ENV=prod \
    -e PYENV=/zn/app/pyenv \
    -e APP_MODELS=/zn/models \
    -e LOG_LEVEL=debug \
    -v /u03/workspaces/qgen-api/config:/zn/app/config \
    --network wd-net \
    qgen-api