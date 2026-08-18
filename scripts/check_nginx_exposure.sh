#!/usr/bin/env bash
set -euo pipefail

CONFIG="${1:-nginx-production.conf}"
[[ -f "$CONFIG" ]] || { echo "NO-GO: nginx config absente: $CONFIG" >&2; exit 1; }

required=(
  'server_name app.autocommerce-clinic.com;'
  'server_name pub.api.autocommerce-clinic.com;'
  'server_name clinic.autocommerce-clinic.local;'
  'server_name api.autocommerce-clinic.com;'
  'location ^~ /api/public/'
  'location ^~ /api/private/ { return 404; }'
  'location ^~ /api/v1/ { return 404; }'
  'allow 10.0.0.0/8;'
  'allow 172.16.0.0/12;'
  'allow 192.168.0.0/16;'
  'deny all;'
  'ssl_certificate     /etc/autocommerce/tls/clinic.fullchain.pem;'
)
for pattern in "${required[@]}"; do
  grep -Fq "$pattern" "$CONFIG" || { echo "NO-GO: règle Nginx absente: $pattern" >&2; exit 1; }
done

public_block_count="$(grep -Fc 'location ^~ /api/private/ { return 404; }' "$CONFIG")"
[[ "$public_block_count" -ge 2 ]] || { echo "NO-GO: refus public/private insuffisant" >&2; exit 1; }

echo "NGINX EXPOSURE PASS: public gateway allowlisted, private core restricted, legacy /api/v1 blocked publicly"
