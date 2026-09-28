-- Upserts keep each dimension member's surrogate key stable across loads.
insert into jira_ai.dim_category (category_no, category, detail)
select category_no, category, detail from jira_ai.ref_categories
on conflict (category_no) do update set category = excluded.category, detail = excluded.detail;

insert into jira_ai.dim_score_anchor (score, general_logic, clarity_anchor)
select score, general_logic, clarity_anchor from jira_ai.ref_score_anchors
on conflict (score) do update set general_logic = excluded.general_logic, clarity_anchor = excluded.clarity_anchor;

insert into jira_ai.dim_agent_archetype (archetype_no, archetype, handles, autonomy, blocked_by)
select archetype_no, archetype, handles, autonomy, blocked_by from jira_ai.ref_agent_archetypes
on conflict (archetype_no) do update set
  archetype = excluded.archetype, handles = excluded.handles,
  autonomy = excluded.autonomy, blocked_by = excluded.blocked_by;

insert into jira_ai.dim_evidence_basis (value, definition)
select value, definition from jira_ai.ref_evidence_basis
on conflict (value) do update set definition = excluded.definition;

insert into jira_ai.dim_knowledge_deflection_anchor (score, knowledge_deflection_anchor)
select score, knowledge_deflection_anchor from jira_ai.ref_knowledge_deflection_anchors
on conflict (score) do update set knowledge_deflection_anchor = excluded.knowledge_deflection_anchor;

insert into jira_ai.fact_jira_request (
  jira_key, primary_category_key, secondary_category_key,
  clarity_score_anchor_key, complexity_score_anchor_key, automation_score_anchor_key,
  knowledge_deflection_anchor_key, agent_archetype_key, evidence_basis_key,
  created_at, resolved_at, duration_days, is_excluded, is_batch, is_project_work,
  automation_logic_score, complexity_score, clarity_score, knowledge_deflection_score
)
select
  j.key, pc.category_key, sc.category_key,
  cl.score_anchor_key, co.score_anchor_key, au.score_anchor_key,
  kd.knowledge_deflection_anchor_key, aa.agent_archetype_key, eb.evidence_basis_key,
  j.created, j.resolved, j.duration_days, j.is_excluded, j.is_batch, j.is_project_work,
  j.automation_logic, j.complexity, j.clarity, j.knowledge_deflection
from jira_ai.jira_requests j
left join jira_ai.dim_category pc on pc.category = j.primary_category
left join jira_ai.dim_category sc on sc.category = j.secondary_category
left join jira_ai.dim_score_anchor cl on cl.score = j.clarity
left join jira_ai.dim_score_anchor co on co.score = j.complexity
left join jira_ai.dim_score_anchor au on au.score = j.automation_logic
left join jira_ai.dim_knowledge_deflection_anchor kd on kd.score = j.knowledge_deflection
left join jira_ai.dim_agent_archetype aa on aa.archetype = j.agent_archetype
left join jira_ai.dim_evidence_basis eb on eb.value = j.evidence_basis
on conflict (jira_key) do update set
  primary_category_key = excluded.primary_category_key,
  secondary_category_key = excluded.secondary_category_key,
  clarity_score_anchor_key = excluded.clarity_score_anchor_key,
  complexity_score_anchor_key = excluded.complexity_score_anchor_key,
  automation_score_anchor_key = excluded.automation_score_anchor_key,
  knowledge_deflection_anchor_key = excluded.knowledge_deflection_anchor_key,
  agent_archetype_key = excluded.agent_archetype_key,
  evidence_basis_key = excluded.evidence_basis_key,
  created_at = excluded.created_at,
  resolved_at = excluded.resolved_at,
  duration_days = excluded.duration_days,
  is_excluded = excluded.is_excluded,
  is_batch = excluded.is_batch,
  is_project_work = excluded.is_project_work,
  automation_logic_score = excluded.automation_logic_score,
  complexity_score = excluded.complexity_score,
  clarity_score = excluded.clarity_score,
  knowledge_deflection_score = excluded.knowledge_deflection_score;
