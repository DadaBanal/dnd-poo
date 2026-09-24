#!/bin/sh
# Alertmanager's start (Path A, M3.3): write its configuration from the site's
# values, check it, then run it. Alerts go to ICT by email through PMC's mail
# relay (PMC_ALERT_EMAIL_TO, _FROM, PMC_ALERT_SMTP), to a Teams channel
# through a Workflows webhook (the secret alert-teams-webhook), both, or, until
# ICT sets one, nowhere: they then show only in Alertmanager itself.
set -eu
config=/tmp/alertmanager.yml
teams=/run/secrets/alert-teams-webhook

{
  cat <<EOF
route:
  receiver: ict
  group_by: [alertname, modality, server, stanza]
  group_wait: 10s
  group_interval: 5m
  repeat_interval: 4h
receivers:
  - name: ict
EOF
  if [ -n "${PMC_ALERT_EMAIL_TO:-}" ]; then
    cat <<EOF
    email_configs:
      - to: '${PMC_ALERT_EMAIL_TO}'
        from: '${PMC_ALERT_EMAIL_FROM:?PMC_ALERT_EMAIL_FROM is not set}'
        smarthost: '${PMC_ALERT_SMTP:?PMC_ALERT_SMTP is not set}'
        require_tls: ${PMC_ALERT_SMTP_TLS:-true}
        send_resolved: true
EOF
  fi
  if [ -s "$teams" ]; then
    cat <<EOF
    msteamsv2_configs:
      - webhook_url_file: $teams
        send_resolved: true
EOF
  fi
} > "$config"

[ -n "${PMC_ALERT_EMAIL_TO:-}" ] || [ -s "$teams" ] ||
  echo "alertmanager: no email relay and no Teams webhook set: alerts show here only" >&2
/bin/amtool check-config "$config" >/dev/null
exec /bin/alertmanager --config.file="$config" --storage.path=/alertmanager
