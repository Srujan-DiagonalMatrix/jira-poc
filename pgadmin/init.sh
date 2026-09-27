#!/bin/sh
set -e
cat > /var/lib/pgadmin/servers.json <<EOF
{
  "Servers": {
    "1": {
      "Name": "JSM Tickets",
      "Group": "Servers",
      "Host": "db",
      "Port": 5432,
      "MaintenanceDB": "$POSTGRES_DB",
      "Username": "$ANALYST_USER",
      "ConnectionParameters": {
        "sslmode": "prefer",
        "connect_timeout": 10,
        "passfile": "/var/lib/pgadmin/pgpass"
      }
    }
  }
}
EOF
printf 'db:5432:*:%s:%s\n' "$ANALYST_USER" "$ANALYST_PASSWORD" > /var/lib/pgadmin/pgpass
chmod 600 /var/lib/pgadmin/pgpass
exec /entrypoint.sh "$@"
