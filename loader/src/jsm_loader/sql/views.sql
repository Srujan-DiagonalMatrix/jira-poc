CREATE VIEW v_request_distribution AS
WITH t AS (
    SELECT coalesce(request_topic, '(blank)') AS topic,
           coalesce(request_type, '(blank)')  AS req_type,
           issue_type
    FROM jira_requests
)
SELECT
    CASE WHEN grouping(topic) = 1 THEN 'Grand Total' ELSE topic END AS request_topic,
    CASE WHEN grouping(topic) = 1 THEN NULL
         WHEN grouping(req_type) = 1 THEN '(all request types)'
         ELSE req_type END                                  AS request_type,
    count(*) FILTER (WHERE issue_type = 'Bug')             AS bug,
    count(*) FILTER (WHERE issue_type = 'Emailed request') AS emailed_request,
    count(*) FILTER (WHERE issue_type = 'General request') AS general_request,
    count(*) FILTER (WHERE issue_type = 'Task')            AS task,
    count(*) FILTER (WHERE issue_type NOT IN ('Bug', 'Emailed request', 'General request', 'Task')) AS other,
    count(*)                                               AS total,
    round(100.0 * count(*) / nullif((SELECT count(*) FROM jira_requests), 0), 1) AS pct_of_all
FROM t
GROUP BY ROLLUP (topic, req_type)
ORDER BY grouping(topic), topic, grouping(req_type) DESC, req_type;

CREATE VIEW v_requests_by_month AS
SELECT
    date_trunc('month', created AT TIME ZONE 'UTC')::date AS month,
    count(*) FILTER (WHERE issue_type = 'Bug')             AS bug,
    count(*) FILTER (WHERE issue_type = 'Emailed request') AS emailed_request,
    count(*) FILTER (WHERE issue_type = 'General request') AS general_request,
    count(*) FILTER (WHERE issue_type = 'Task')            AS task,
    count(*) FILTER (WHERE issue_type NOT IN ('Bug', 'Emailed request', 'General request', 'Task')) AS other,
    count(*)                                               AS total
FROM jira_requests
GROUP BY 1
ORDER BY 1;

CREATE VIEW v_exec_summary_check AS
WITH ref AS (
    SELECT max(created) AS as_of FROM jira_requests
),
t AS (
    SELECT r.*, (SELECT as_of FROM ref) - r.created AS age,
           r.linked_issues ~ '(^|;)\s*REVAPPS-5690\s*(;|$)' AS links_revapps_5690
    FROM jira_requests r
),
metrics (sort_order, metric, data_value, slide_value) AS (
    SELECT 1, 'Total tickets', count(*)::numeric, 5344 FROM t
    UNION ALL SELECT 2, 'General requests', count(*) FILTER (WHERE issue_type = 'General request'), 4929 FROM t
    UNION ALL SELECT 3, 'Bugs', count(*) FILTER (WHERE issue_type = 'Bug'), 395 FROM t
    UNION ALL SELECT 4, 'Unprioritized tickets', count(*) FILTER (WHERE priority = 'Unprioritized'), 4962 FROM t
    UNION ALL SELECT 5, 'Tickets without severity', count(*) FILTER (WHERE severity IS NULL), 5119 FROM t
    UNION ALL SELECT 6, 'Unassigned tickets', count(*) FILTER (WHERE assignee IS NULL), 2542 FROM t
    UNION ALL SELECT 7, 'Unassigned and unresolved', count(*) FILTER (WHERE assignee IS NULL AND resolved IS NULL), 296 FROM t
    UNION ALL SELECT 8, 'Average age of unassigned unresolved (days)',
        round(avg(extract(epoch FROM age) / 86400) FILTER (WHERE assignee IS NULL AND resolved IS NULL), 1), 237 FROM t
    UNION ALL SELECT 9, 'Revenue Applications Support unassigned',
        count(*) FILTER (WHERE request_type = 'Revenue Applications Support' AND assignee IS NULL), 2260 FROM t
    UNION ALL SELECT 10, 'Revenue Applications Support active and 60+ days old',
        count(*) FILTER (WHERE request_type = 'Revenue Applications Support'
                           AND status IN ('Open', 'In Progress', 'Under Review')
                           AND age >= interval '60 days'), 478 FROM t
    UNION ALL SELECT 11, 'Tickets linked to REVAPPS-5690', count(*) FILTER (WHERE links_revapps_5690), 25 FROM t
    UNION ALL SELECT 12, 'Tickets linked to REVAPPS-5690 still unresolved',
        count(*) FILTER (WHERE links_revapps_5690 AND resolved IS NULL), 24 FROM t
)
SELECT metric, data_value, slide_value, data_value = slide_value AS matches, (SELECT as_of FROM ref) AS measured_at
FROM metrics
ORDER BY sort_order;
