#!/bin/sh
set -ex

SERVER_DIR="${HOME}"
STARLORD_DIR="${SERVER_DIR}/StarLord"
STARLORD_MAIN="${STARLORD_DIR}/__main__.py"

if [ -f "${STARLORD_MAIN}" ]; then
    exec /usr/bin/python3 "${STARLORD_MAIN}"
    exit 1
fi

if [ -d "${STARLORD_DIR}" ]; then
    rm -rf "${STARLORD_DIR}"
fi

cp -r /opt/StarLord "${STARLORD_DIR}"

exec /usr/bin/python3 "${STARLORD_MAIN}"
exit 1
