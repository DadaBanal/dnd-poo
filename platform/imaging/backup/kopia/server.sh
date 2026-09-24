#!/bin/sh
# The R740xd's copy of the DICOM files (Path A, M3): a Kopia repository server
# on the second building's disks. The primary connects as orthanc@pmc-primary
# and may APPEND snapshots and READ its policy, never delete a snapshot or
# shorten retention: a compromised primary cannot destroy its own backups.
# Retention and maintenance run here, as the repository's owner.
#
# First start: create the repository (encrypted with kopia-repo-password),
# the primary's user, and the retention policy. Every start: enforce the ACL.
set -eu
export KOPIA_PASSWORD="$(cat /run/secrets/kopia-repo-password)"
cfg=/app/config/repository.config
k="kopia --config-file=$cfg --log-dir=/app/config/logs"

if [ ! -f "$cfg" ]; then
  $k repository create filesystem --path=/repo --override-hostname=r740xd --override-username=owner
  $k server user add orthanc@pmc-primary --user-password="$(cat /run/secrets/kopia-client-password)"
  $k policy set --global --keep-latest=10 --keep-daily=14 --keep-weekly=8 --keep-monthly=24 --keep-annual=10
fi

[ -n "$($k server acl list 2>/dev/null)" ] || $k server acl enable
# No FULL access to snapshots or policies for anyone but the owner here.
for id in $($k server acl list | awk '/access:FULL/ && (/type=snapshot/ || /type=policy/) {sub("id:","",$1); print $1}'); do
  $k server acl delete "$id" --delete
done
$k server acl list | grep -q 'access:APPEND target:type=snapshot' ||
  $k server acl add --user='*@*' --access=APPEND --target='type=snapshot,username=OWN_USER,hostname=OWN_HOST'
$k server acl list | grep -q 'access:READ target:type=policy' ||
  $k server acl add --user='*@*' --access=READ --target='type=policy,username=OWN_USER,hostname=OWN_HOST'

exec $k server start --address=0.0.0.0:51515 \
  --tls-cert-file=/run/secrets/kopia-server-cert --tls-key-file=/run/secrets/kopia-server-key \
  --server-control-username=control --server-control-password="$(cat /run/secrets/kopia-control-password)" \
  --server-username=ui --server-password="$(cat /run/secrets/kopia-control-password)"
