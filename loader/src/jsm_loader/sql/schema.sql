-- Objects from earlier versions of this package, which kept everything in public.
DROP VIEW IF EXISTS public.v_exec_summary_check, public.v_requests_by_month, public.v_request_distribution;
DROP TABLE IF EXISTS
    public.ticket_links, public.ref_review_fields, public.export_metadata,
    public.exec_summary_slide, public.source_files;
DROP TABLE IF EXISTS
    public.jira_requests, public.ref_categories, public.ref_score_anchors,
    public.ref_agent_archetypes, public.ref_evidence_basis, public.ref_knowledge_deflection_anchors;

create schema if not exists jira_ai;
set search_path = jira_ai, public;

create table if not exists load_jira_requests_raw (
  load_jira_requests_raw_id bigint generated always as identity primary key,
  batch_id uuid not null,
  source_file_name text not null,
  source_sheet_name text not null default 'Jira Requests',
  source_row_number integer not null check (source_row_number > 0),
  source_payload jsonb not null,
  loaded_at timestamptz not null default now(),
  unique (batch_id, source_sheet_name, source_row_number)
);

create table if not exists load_reference_rows_raw (
  load_reference_rows_raw_id bigint generated always as identity primary key,
  batch_id uuid not null,
  source_file_name text not null,
  source_sheet_name text not null default 'Request Review Design',
  source_label text not null check (source_label in ('TABLE A','TABLE B','TABLE C','TABLE D','TABLE E')),
  source_row_number integer not null check (source_row_number > 0),
  source_payload jsonb not null,
  loaded_at timestamptz not null default now(),
  unique (batch_id, source_label, source_row_number)
);

create table if not exists stg_jira_requests (
  batch_id uuid not null,
  source_row_number integer not null,
  key text not null,
  issue_type text not null,
  summary text,
  description text,
  request_type text,
  request_topic text,
  assignee text,
  status text not null,
  created timestamptz not null,
  reporter text,
  synced_to_jira boolean,
  resolved timestamptz,
  duration_days numeric(14,4),
  linked_issues text,
  comment_summary text,
  priority text,
  severity text,
  is_excluded boolean not null default false,
  exclude_reason text,
  primary_category text,
  secondary_category text,
  sub_type text,
  is_batch boolean,
  is_project_work boolean,
  clarity smallint,
  complexity smallint,
  knowledge_deflection smallint,
  automation_logic smallint,
  action_class text,
  approval_required text,
  agent_archetype text,
  confidence text,
  rationale text,
  data_domain text,
  reversibility text,
  evidence_basis text,
  validation_status text not null default 'PENDING' check (validation_status in ('PENDING','VALID','QUARANTINED')),
  validation_message text,
  primary key (batch_id, source_row_number)
);

-- The blueprint's stg_ref_* definitions were cut off at the page edge; these mirror the ref_* tables plus batch_id.
create table if not exists stg_ref_categories (batch_id uuid not null, category_no integer not null, category text not null, detail text, primary key (batch_id, category_no));
create table if not exists stg_ref_score_anchors (batch_id uuid not null, score smallint not null check (score between 1 and 5), general_logic text, clarity_anchor text, primary key (batch_id, score));
create table if not exists stg_ref_agent_archetypes (batch_id uuid not null, archetype_no integer not null, archetype text not null, handles text, autonomy text, blocked_by text, primary key (batch_id, archetype_no));
create table if not exists stg_ref_evidence_basis (batch_id uuid not null, value text not null, definition text, primary key (batch_id, value));
create table if not exists stg_ref_knowledge_deflection_anchors (batch_id uuid not null, score smallint not null check (score between 1 and 5), knowledge_deflection_anchor text, primary key (batch_id, score));

create table if not exists ref_categories (
  category_no integer primary key,
  category text not null unique,
  detail text
);
create table if not exists ref_score_anchors (
  score smallint primary key check (score between 1 and 5),
  general_logic text,
  clarity_anchor text
);
create table if not exists ref_agent_archetypes (
  archetype_no integer primary key,
  archetype text not null unique,
  handles text,
  autonomy text,
  blocked_by text
);
create table if not exists ref_evidence_basis (
  value text primary key,
  definition text
);
create table if not exists ref_knowledge_deflection_anchors (
  score smallint primary key check (score between 1 and 5),
  knowledge_deflection_anchor text
);

create table if not exists jira_requests (
  key text primary key,
  issue_type text not null,
  summary text,
  description text,
  request_type text,
  request_topic text,
  assignee text,
  status text not null,
  created timestamptz not null,
  reporter text,
  synced_to_jira boolean,
  resolved timestamptz,
  duration_days numeric(14,4),
  linked_issues text,
  comment_summary text,
  priority text,
  severity text,
  is_excluded boolean not null default false,
  exclude_reason text,
  primary_category text,
  secondary_category text,
  sub_type text,
  is_batch boolean,
  is_project_work boolean,
  clarity smallint,
  complexity smallint,
  knowledge_deflection smallint,
  automation_logic smallint,
  action_class text,
  approval_required text,
  agent_archetype text,
  confidence text,
  rationale text,
  data_domain text,
  reversibility text,
  evidence_basis text,
  loaded_batch_id uuid not null,
  loaded_at timestamptz not null default now(),
  check (is_excluded or primary_category is not null),
  check ((not is_excluded and exclude_reason is null) or is_excluded),
  check (clarity is null or clarity between 1 and 5),
  check (complexity is null or complexity between 1 and 5),
  check (knowledge_deflection is null or knowledge_deflection between 1 and 5),
  check (automation_logic is null or automation_logic between 1 and 5),
  check (action_class is null or action_class in ('read-only','standard write','privileged write','config change')),
  check (approval_required is null or approval_required in ('none','manager','segregation-of-duties')),
  check (confidence is null or confidence in ('low','medium','high')),
  check (data_domain is null or data_domain in ('permissions','customer record','billing record','configuration','reporting object','none')),
  check (reversibility is null or reversibility in ('easy','hard','irreversible')),
  check (duration_days is null or duration_days >= 0),
  check (resolved is not null or duration_days is null),
  foreign key (primary_category) references ref_categories(category),
  foreign key (secondary_category) references ref_categories(category),
  foreign key (clarity) references ref_score_anchors(score),
  foreign key (complexity) references ref_score_anchors(score),
  foreign key (automation_logic) references ref_score_anchors(score),
  foreign key (knowledge_deflection) references ref_knowledge_deflection_anchors(score),
  foreign key (agent_archetype) references ref_agent_archetypes(archetype),
  foreign key (evidence_basis) references ref_evidence_basis(value)
);

create table if not exists dim_category (
  category_key bigint generated always as identity primary key,
  category_no integer not null unique,
  category text not null unique,
  detail text
);
create table if not exists dim_score_anchor (
  score_anchor_key bigint generated always as identity primary key,
  score smallint not null unique check (score between 1 and 5),
  general_logic text,
  clarity_anchor text
);
create table if not exists dim_agent_archetype (
  agent_archetype_key bigint generated always as identity primary key,
  archetype_no integer not null unique,
  archetype text not null unique,
  handles text,
  autonomy text,
  blocked_by text
);
create table if not exists dim_evidence_basis (
  evidence_basis_key bigint generated always as identity primary key,
  value text not null unique,
  definition text
);
create table if not exists dim_knowledge_deflection_anchor (
  knowledge_deflection_anchor_key bigint generated always as identity primary key,
  score smallint not null unique check (score between 1 and 5),
  knowledge_deflection_anchor text
);

create table if not exists fact_jira_request (
  jira_request_fact_key bigint generated always as identity primary key,
  jira_key text not null unique references jira_requests(key),
  primary_category_key bigint references dim_category(category_key),
  secondary_category_key bigint references dim_category(category_key),
  clarity_score_anchor_key bigint references dim_score_anchor(score_anchor_key),
  complexity_score_anchor_key bigint references dim_score_anchor(score_anchor_key),
  automation_score_anchor_key bigint references dim_score_anchor(score_anchor_key),
  knowledge_deflection_anchor_key bigint references dim_knowledge_deflection_anchor(knowledge_deflection_anchor_key),
  agent_archetype_key bigint references dim_agent_archetype(agent_archetype_key),
  evidence_basis_key bigint references dim_evidence_basis(evidence_basis_key),
  created_at timestamptz not null,
  resolved_at timestamptz,
  duration_days numeric(14,4),
  is_excluded boolean not null,
  is_batch boolean,
  is_project_work boolean,
  request_count integer not null default 1 check (request_count = 1),
  automation_logic_score smallint check (automation_logic_score between 1 and 5),
  complexity_score smallint check (complexity_score between 1 and 5),
  clarity_score smallint check (clarity_score between 1 and 5),
  knowledge_deflection_score smallint check (knowledge_deflection_score between 1 and 5),
  check (duration_days is null or duration_days >= 0),
  check (resolved_at is not null or duration_days is null)
);

create index if not exists ix_jira_requests_reporting on jira_requests (is_excluded, primary_category, automation_logic, status);
create index if not exists ix_jira_requests_lifecycle on jira_requests (status, created, resolved);
create index if not exists ix_fact_jira_request_reporting on fact_jira_request (is_excluded, automation_logic_score, primary_category_key);
create index if not exists ix_fact_jira_request_lifecycle on fact_jira_request (created_at, resolved_at);

create or replace view vw_ai_opportunity as
select
  f.jira_key, c.category as primary_category, a.archetype as agent_archetype,
  j.sub_type, j.action_class, j.approval_required, j.reversibility, j.confidence,
  f.automation_logic_score, f.complexity_score, f.knowledge_deflection_score,
  f.duration_days,
  case
    -- The blueprint's label for this branch was cut off at the page edge.
    when f.automation_logic_score >= 4 and lower(coalesce(j.approval_required,'')) = 'none' and lower(coalesce(j.reversibility,'')) = 'easy' then 'autonomous'
    when f.automation_logic_score >= 4 then 'execute_with_approval'
    when f.automation_logic_score >= 3 then 'assist_only'
    else 'human_led'
  end as autonomy_opportunity
from fact_jira_request f
join jira_requests j on j.key = f.jira_key
left join dim_category c on c.category_key = f.primary_category_key
left join dim_agent_archetype a on a.agent_archetype_key = f.agent_archetype_key
where not f.is_excluded;

create or replace view vw_existing_data_validation_report as
select
  batch_id,
  validation_status,
  count(*) as row_count,
  string_agg(distinct validation_message, ' | ') filter (where validation_message is not null) as validation_messages
from stg_jira_requests
group by batch_id, validation_status;
