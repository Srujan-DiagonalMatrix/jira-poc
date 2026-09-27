#!/bin/sh
set -eu
api=http://localhost:3000/api

/app/run_metabase.sh &
metabase=$!
# Forward docker stop to Metabase so it closes its H2 database cleanly.
trap 'kill -TERM "$metabase"; wait "$metabase"' TERM INT

until curl -sf "$api/health" >/dev/null; do
    kill -0 "$metabase" 2>/dev/null || exit 1
    sleep 2
done

properties=$(curl -sf "$api/session/properties")
case $properties in
    *'"has-user-setup":false'*)
        token=$(printf '%s' "$properties" | sed -n 's/.*"setup-token":"\([^"]*\)".*/\1/p')
        session=$(curl -sf -X POST "$api/setup" -H 'Content-Type: application/json' -d "{
            \"token\": \"$token\",
            \"user\": {\"email\": \"$METABASE_EMAIL\", \"password\": \"$METABASE_PASSWORD\",
                       \"first_name\": \"JSM\", \"last_name\": \"Admin\"},
            \"prefs\": {\"site_name\": \"JSM Tickets\", \"site_locale\": \"en\"}
        }" | sed -n 's/.*"id":"\([^"]*\)".*/\1/p')
        curl -sf -X POST "$api/database" -H 'Content-Type: application/json' \
            -H "X-Metabase-Session: $session" -d "{
            \"engine\": \"postgres\",
            \"name\": \"JSM Tickets\",
            \"details\": {\"host\": \"db\", \"port\": 5432, \"dbname\": \"$POSTGRES_DB\",
                          \"user\": \"$ANALYST_USER\", \"password\": \"$ANALYST_PASSWORD\", \"ssl\": false}
        }" >/dev/null
        echo "init.sh: created the Metabase login and connected the JSM Tickets database"
        ;;
esac

wait "$metabase"
