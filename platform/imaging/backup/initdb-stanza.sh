#!/bin/sh
# A new cluster's first start only (docker-entrypoint-initdb.d, after the
# databases exist): create its pgBackRest stanza in every configured
# repository, so write-ahead log archiving works from the first segment.
set -eu
pgbackrest --stanza="$PMC_BACKUP_STANZA" stanza-create
