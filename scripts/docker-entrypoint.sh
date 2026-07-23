#!/bin/sh
set -eu

private_key_path="${AUTH_JWT__PRIVATE_KEY_PATH:-certs/private.pem}"
public_key_path="${AUTH_JWT__PUBLIC_KEY_PATH:-certs/public.pem}"

mkdir -p "$(dirname "$private_key_path")" "$(dirname "$public_key_path")"

if [ ! -f "$private_key_path" ] || [ ! -f "$public_key_path" ]; then
    openssl genrsa -out "$private_key_path" 2048
    openssl rsa -in "$private_key_path" -pubout -out "$public_key_path"
fi

exec "$@"
