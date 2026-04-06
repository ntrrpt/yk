#!/bin/bash
USER_ID=${UID:-9001}
GROUP_ID=${GID:-9001}

echo "uid: $USER_ID"
echo "gid: $GROUP_ID"

mkdir /.cache
chown -R $USER_ID:$GROUP_ID /yk
chown -R $USER_ID:$GROUP_ID /.cache
chown -R $USER_ID:$GROUP_ID $YK_INPUT
chown -R $USER_ID:$GROUP_ID $YK_OUTPUT

CMD="gosu $USER_ID python -m yk"
echo "cmd: $CMD $*"
$CMD "$@"