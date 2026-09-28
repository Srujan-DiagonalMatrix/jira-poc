insert into jira_ai.ref_categories (category_no, category, detail)
select category_no, category, detail
from jira_ai.stg_ref_categories
where batch_id = current_setting('jira_ai.batch_id')::uuid
on conflict (category_no) do update set category = excluded.category, detail = excluded.detail;

insert into jira_ai.ref_score_anchors (score, general_logic, clarity_anchor)
select score, general_logic, clarity_anchor
from jira_ai.stg_ref_score_anchors
where batch_id = current_setting('jira_ai.batch_id')::uuid
on conflict (score) do update set general_logic = excluded.general_logic, clarity_anchor = excluded.clarity_anchor;

insert into jira_ai.ref_agent_archetypes (archetype_no, archetype, handles, autonomy, blocked_by)
select archetype_no, archetype, handles, autonomy, blocked_by
from jira_ai.stg_ref_agent_archetypes
where batch_id = current_setting('jira_ai.batch_id')::uuid
on conflict (archetype_no) do update set
  archetype = excluded.archetype, handles = excluded.handles,
  autonomy = excluded.autonomy, blocked_by = excluded.blocked_by;

insert into jira_ai.ref_evidence_basis (value, definition)
select value, definition
from jira_ai.stg_ref_evidence_basis
where batch_id = current_setting('jira_ai.batch_id')::uuid
on conflict (value) do update set definition = excluded.definition;

insert into jira_ai.ref_knowledge_deflection_anchors (score, knowledge_deflection_anchor)
select score, knowledge_deflection_anchor
from jira_ai.stg_ref_knowledge_deflection_anchors
where batch_id = current_setting('jira_ai.batch_id')::uuid
on conflict (score) do update set knowledge_deflection_anchor = excluded.knowledge_deflection_anchor;
