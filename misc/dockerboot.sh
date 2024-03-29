#!/bin/sh
set -ex

SERVER_DIR="${HOME}"
STARLORD_DIR="${SERVER_DIR}/StarLord"
STARLORD_COPY_DONE_FILE="${STARLORD_DIR}/.copydone"

if [ -f "${STARLORD_COPY_DONE_FILE}" ]; then
    exec /usr/bin/python3 "${STARLORD_DIR}"
    exit 1
fi

if [ -d "${STARLORD_DIR}" ]; then
    rm -rf "${STARLORD_DIR}"
fi

cp -r /opt/StarLord "${STARLORD_DIR}"
touch "${STARLORD_COPY_DONE_FILE}"

exec /usr/bin/python3 "${STARLORD_DIR}"
exit 1
