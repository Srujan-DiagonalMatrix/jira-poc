# JSM tickets database

This package loads your JSM ticket data into a PostgreSQL database on your computer, so you can browse, query and chart it in your web browser.

It loads **JSM Data - Sept 21 v2 - scored.xlsx** from `data/source/`: all 5,344 tickets with their AI review scores, and the tables from its "Request Review Design" sheet. The raw Jira export, **JSM Data - Sept 21.xlsx**, is in the same folder for download only; it isn't loaded. Both files are included, so there's nothing to add.

Everything runs on your computer; nothing is sent anywhere.

## What you need

- [Docker Desktop](https://www.docker.com/products/docker-desktop/), running.
- About 4 GB of free disk space.
- About 2 GB of free memory while it runs. Metabase alone uses about 1 GB.
- An internet connection for the first start.

## Get the project

```sh
git clone -b jira-data https://github.com/Srujan-DiagonalMatrix/jira-poc.git
cd jira-poc
```

Without git: on the GitHub page, switch the branch to **jira-data**, then choose **Code → Download ZIP** and unzip it.

## Start

Open a terminal in the project folder.

1. The first time only, create your settings file (`.env`) with new passwords:

   ```sh
   sh scripts/init-env.sh
   ```

2. Start everything:

   ```sh
   docker compose up -d
   ```

The first start takes a few minutes; later starts take seconds. After restarting your computer, run step 2 again.

On Windows, run step 1 in Git Bash or WSL.

## Look at the data

1. Open <http://localhost:5050>. No login is needed.
2. In the left panel, open **Servers → JSM Tickets → Databases → jsm → Schemas → public → Tables**.
3. Right-click a table and choose **View/Edit Data → All Rows**.
4. To write SQL, select **jsm**, choose **Tools → Query Tool**, type a query and press **F5**. The download button saves the results as CSV.

The connection is read-only, so you can't change data by accident. Dates and times are in UTC.

To download the original files, open <http://localhost:8080>.

## Charts and dashboards

Metabase lets you build charts and dashboards by clicking, without SQL.

1. Open <http://localhost:3000>. Right after a start, it can take a minute or two before the page opens.
2. Log in with `METABASE_EMAIL` and `METABASE_PASSWORD` from the `.env` file in this folder.
3. Click **+ New → Question**, then pick **JSM Tickets → Jira Requests**.
4. Choose what to count and how to group it, for example **Count of rows** by **Primary Category**, and click **Visualize**.
5. Click **Save** to keep the chart. You can add saved charts to a dashboard.

Metabase uses the same read-only connection as pgAdmin, and it keeps your saved charts and dashboards between starts.

## What's in the database

| Name | What it holds |
|---|---|
| `jira_requests` | One row per ticket, with the AI review scores (the sheet's REVIEW SCHEMA). Each review column's description is its note from that schema. `duration_days` is calculated from `created` and `resolved`. |
| `ref_categories` | TABLE A: the categories used in `primary_category` and `secondary_category`. |
| `ref_score_anchors` | TABLE B: what each score from 1 to 5 means. |
| `ref_agent_archetypes` | TABLE C: the AI agent types used in `agent_archetype`. |
| `ref_evidence_basis` | TABLE D: the values used in `evidence_basis`. |
| `ref_knowledge_deflection_anchors` | TABLE E: what each `knowledge_deflection` score from 1 to 5 means. |

For a map of the tables and all their columns, open `docs/architecture.html` in your browser.

## Example queries

Tickets per status:

```sql
SELECT status, count(*) AS tickets
FROM jira_requests
GROUP BY status
ORDER BY tickets DESC;
```

The 10 assignees with the most tickets:

```sql
SELECT coalesce(assignee, '(unassigned)') AS assignee, count(*) AS tickets
FROM jira_requests
GROUP BY 1
ORDER BY tickets DESC
LIMIT 10;
```

Tickets per AI agent type:

```sql
SELECT a.archetype_no, a.archetype, a.autonomy, count(r.key) AS tickets
FROM ref_agent_archetypes a
LEFT JOIN jira_requests r ON r.agent_archetype = a.archetype
GROUP BY a.archetype_no, a.archetype, a.autonomy
ORDER BY a.archetype_no;
```

Tickets created per month:

```sql
SELECT date_trunc('month', created AT TIME ZONE 'UTC')::date AS month, count(*) AS tickets
FROM jira_requests
GROUP BY 1
ORDER BY 1;
```

The tickets linked to REVAPPS-5690:

```sql
SELECT key, summary, status, created, resolved
FROM jira_requests
WHERE linked_issues ~ '(^|;)\s*REVAPPS-5690\s*(;|$)'
ORDER BY created;
```

## Connect from a desktop SQL tool

In a tool such as DBeaver or TablePlus, use:

| Setting | Value |
|---|---|
| Host | `127.0.0.1` |
| Port | `5433` (`DB_PORT` in `.env`) |
| Database | `jsm` |
| User | `jira_reader` (`ANALYST_USER` in `.env`) |
| Password | `ANALYST_PASSWORD` in `.env` |

## Load new files

1. Replace the scored workbook in `data/source/`. The file name doesn't matter.
2. Run one of these:

   - `docker compose run --rm loader` loads the files from inside Docker.
   - `sh scripts/load.sh` loads them from your computer into the Docker database. It needs Python 3.9 or newer, and the first run takes about a minute to install the loader.

Either one ends with "load complete". You can ignore its warning that it is ignoring the raw export. If a file has a problem, it names the file, row and column, and nothing in the database changes.

## Get updates

When a new version is published, run this in the project folder:

```sh
git pull
docker compose up -d --build
```

`--build` makes Docker use the updated loader.

## Stop

- `docker compose down` stops everything and keeps the data.
- `docker compose down -v` also deletes the database and Metabase's saved charts and dashboards. The next start loads the files again.

## Change ports or passwords

All user names, passwords and ports are in the `.env` file in this folder. Open it in a text editor, change the values (letters, digits, hyphens and underscores only), then run `docker compose up -d`.

The owner settings (`POSTGRES_…`) only apply when the database is first created. To change them later, run `docker compose down -v` first. The next start rebuilds the database from `data/source/`.

The Metabase login (`METABASE_EMAIL` and `METABASE_PASSWORD`) only applies when Metabase first starts. After that, change it in Metabase's account settings. If you change `ANALYST_PASSWORD`, also change it in Metabase under **Admin settings → Databases → JSM Tickets**.

Keep `.env` private: it holds the passwords. If it's missing, run `sh scripts/init-env.sh` to create one with new passwords.

## Troubleshooting

**"port is already allocated".** Another program is using port 5433, 5050, 8080 or 3000. Choose another port in `.env` and run `docker compose up -d` again.

**The loader failed, or pgAdmin doesn't start.** Run `docker compose logs loader`. The last lines name the file, row and column with the problem. Fix the file, then run `docker compose run --rm loader` and `docker compose up -d`.

**Metabase doesn't open.** It takes a minute or two to start. Run `docker compose logs metabase` to see how far it has got.
