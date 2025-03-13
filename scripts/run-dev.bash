#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pushd "${SCRIPT_DIR}/.." > /dev/null || exit $?

# run 'poetry run whisperserve' and pass all args
dotenvx run --env-file=.env.local -- poetry run whisperserve "$@"

return_code=$?

popd > /dev/null || exit $?

exit $return_code