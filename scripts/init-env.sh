#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

# Metabase rejects passwords without a digit.
new_password() {
    while :; do
        password=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24)
        case $password in
            *[0-9]*) printf '%s' "$password"; return ;;
        esac
    done
}

if [ ! -f .env ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        case $line in
            *_PASSWORD=*) printf '%s=%s\n' "${line%%=*}" "$(new_password)" ;;
            *) printf '%s\n' "$line" ;;
        esac
    done < .env.example > .env
    chmod 600 .env
    echo "Created .env with new passwords."
    exit 0
fi

if [ -n "$(tail -c 1 .env)" ]; then
    echo >> .env
fi
added=""
while IFS= read -r line || [ -n "$line" ]; do
    case $line in
        '' | '#'*) continue ;;
    esac
    key=${line%%=*}
    grep -q "^$key=" .env && continue
    case $key in
        *_PASSWORD) printf '%s=%s\n' "$key" "$(new_password)" >> .env ;;
        *) printf '%s\n' "$line" >> .env ;;
    esac
    added="$added $key"
done < .env.example
chmod 600 .env
if [ -n "$added" ]; then
    echo "Added to .env:$added"
else
    echo ".env already has every setting."
fi
