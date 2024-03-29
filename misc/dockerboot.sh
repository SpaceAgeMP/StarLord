#!/bin/bash
set -euo pipefail
set -x

SERVER_DIR="${HOME}"
STARLORD_DIR="${SERVER_DIR}/StarLord"
STARLORD_COPY_DONE_FILE="${STARLORD_DIR}/.copydone"

exec_starlord() {
    exec /usr/bin/python3 "${STARLORD_DIR}"
    exit 1
}

case "${ENABLE_SELF_UPDATE##0}" in
    "1"|"true"|"True"|"TRUE"|"yes"|"Yes"|"YES")
        export ENABLE_SELF_UPDATE=true
        if [ -f "${STARLORD_COPY_DONE_FILE}" ]; then
            exec_starlord
        fi

        if [ -d "${STARLORD_DIR}" ]; then
            rm -rf "${STARLORD_DIR}"
        fi

        cp -r /opt/StarLord "${STARLORD_DIR}"
        touch "${STARLORD_COPY_DONE_FILE}"
        exec_starlord
        ;;
    "0"|"false"|"False"|"FALSE"|"no"|"No"|"NO")
        export ENABLE_SELF_UPDATE=false
        rsync --exclude=.git --exclude=.github --exclude=misc --delete -av /opt/StarLord/ "${STARLORD_DIR}/"
        exec_starlord
        ;;
    *)
        echo "ENABLE_SELF_UPDATE is set to invalid value"
        exit 2
esac
