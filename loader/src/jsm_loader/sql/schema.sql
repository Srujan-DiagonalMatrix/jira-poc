DROP VIEW IF EXISTS v_exec_summary_check, v_requests_by_month, v_request_distribution;
-- Tables from earlier versions, dropped so a reload leaves only the tables below.
DROP TABLE IF EXISTS
    ticket_links, ref_review_fields, export_metadata, exec_summary_slide, source_files;
DROP TABLE IF EXISTS
    jira_requests, ref_categories, ref_score_anchors, ref_agent_archetypes, ref_evidence_basis,
    ref_knowledge_deflection_anchors;

CREATE TABLE jira_requests (
    issue_type           text        NOT NULL,
    key                  text        PRIMARY KEY,
    summary              text,
    description          text,
    request_type         text,
    request_topic        text,
    assignee             text,
    status               text        NOT NULL,
    created              timestamptz NOT NULL,
    reporter             text,
    synced_to_jira       boolean     NOT NULL,
    resolved             timestamptz,
    duration_days        numeric(8, 2) GENERATED ALWAYS AS
                             (round((extract(epoch FROM resolved - created) / 86400)::numeric, 2)) STORED,
    linked_issues        text,
    comment_summary      text,
    priority             text,
    severity             text,
    is_excluded          boolean     NOT NULL,
    exclude_reason       text,
    primary_category     text,
    secondary_category   text,
    sub_type             text,
    is_batch             boolean,
    is_project_work      boolean,
    clarity              smallint    CHECK (clarity BETWEEN 1 AND 5),
    complexity           smallint    CHECK (complexity BETWEEN 1 AND 5),
    knowledge_deflection smallint    CHECK (knowledge_deflection BETWEEN 1 AND 5),
    automation_logic     smallint    CHECK (automation_logic BETWEEN 1 AND 5),
    action_class         text,
    approval_required    text,
    agent_archetype      text,
    confidence           text,
    rationale            text,
    data_domain          text,
    reversibility        text,
    evidence_basis       text
);

CREATE TABLE ref_categories (
    category_no smallint PRIMARY KEY,
    category    text     NOT NULL UNIQUE,
    detail      text
);

CREATE TABLE ref_score_anchors (
    score          smallint PRIMARY KEY CHECK (score BETWEEN 1 AND 5),
    general_logic  text,
    clarity_anchor text
);

CREATE TABLE ref_agent_archetypes (
    archetype_no smallint PRIMARY KEY,
    archetype    text     NOT NULL UNIQUE,
    handles      text,
    autonomy     text,
    blocked_by   text
);

CREATE TABLE ref_evidence_basis (
    value      text PRIMARY KEY,
    definition text
);

CREATE TABLE ref_knowledge_deflection_anchors (
    score                       smallint PRIMARY KEY CHECK (score BETWEEN 1 AND 5),
    knowledge_deflection_anchor text
);

COMMENT ON TABLE jira_requests IS 'One row per Jira ticket from the "Jira Requests" sheet of the scored workbook, including the AI review scores.';
COMMENT ON TABLE ref_categories IS 'Table A: the categories used by primary_category and secondary_category.';
COMMENT ON TABLE ref_score_anchors IS 'Table B: what each 1-5 score means.';
COMMENT ON TABLE ref_agent_archetypes IS 'Table C: the AI agent archetypes used by agent_archetype.';
COMMENT ON TABLE ref_evidence_basis IS 'Table D: the values used by evidence_basis.';
COMMENT ON TABLE ref_knowledge_deflection_anchors IS 'Table E: what each 1-5 knowledge_deflection score means.';
COMMENT ON COLUMN jira_requests.duration_days IS 'Days from created to resolved.';
