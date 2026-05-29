# Task Brief Template
PROGRAMMATIC_HARNESS_GENERATION

Default: do not copy this whole template by hand. Create new task briefs with:

```powershell
harness-engine/.dev-harness/scripts/new-task-brief.ps1
```

Use this file as the schema reference when the generator lacks a field. If a task brief is hand-written, record why the generator was not sufficient.

��ƽ�����������Ƶ� `harness-engine/.dev-harness/task-briefs/NNN-YYYY-MM-DD-short-name.md`��

## Intent

���ʲô���⣬Ϊʲô��������

## Task Status

Task Status: UNCLAIMED

- Architect:
- Created At:
- Claimed By:
- Claimed At:
- Completed At:
- Status Note:

Status values:

- `UNCLAIMED`: ready for `ִ��task`.
- `CLAIMED`: an implementer is working on it.
- `DONE`: implementation finished and receipt returned.
- `BLOCKED`: implementer stopped with a blocker.

Short-command rule:

- `дtask` creates or updates a brief and leaves it `UNCLAIMED`.
- `ִ��task` claims the latest `UNCLAIMED` brief before editing scoped files.

## Previous Task Acceptance

Required when this brief is created via `дtask`.

- Previous task:
- Previous status:
- Review artifact:
- Receipt artifact:
- Verdict:
- Gate evidence:
- Residual risks:
- Impact on this task:

If the previous completed task lacks receipt/review/gate evidence, do not write
the next task. Return a blocker or complete review first.

## Run Type

ѡ��

- DOCS_ONLY
- LOCAL_CODE
- ENGINE_CRITICAL
- HARNESS_RUNTIME
- META_HARNESS
- CONSTITUTION
- RUNTIME_ARTIFACT

## Layer

ѡ��`harness-engine/.dev-harness`��`harness-engine`��`meta`��`constitution`��`docs`��`data`��

## Risk Class

LOW / MEDIUM / HIGH / BLOCKED_WITHOUT_APPROVAL

## Goal

���������

## Non-Goals

�����񲻻�ı�ʲô��

## Files Expected

- `path/to/file`

## Scope Contract

Allowed files or paths:

- `path/to/file`

Forbidden files or paths:

- `path/to/forbidden-file`

Allowed operations:

- edit existing code
- add targeted tests

Forbidden operations unless explicitly approved:

- opportunistic refactors
- broad formatting-only changes
- dependency or lockfile changes
- public API changes
- schema/data format changes
- generated artifact rewrites
- secret/config rewrites
- changes outside the allowed file list

If the task requires a forbidden operation or an out-of-scope file, stop and
return a blocker instead of expanding scope.

## Implementer Context Package

When this brief is handed to a lower-cost implementer, include only:

- this task brief;
- the minimal relevant code snippets or files;
- the expected verification commands;
- `templates/execution-receipt-template.md`.

Do not include raw brainstorm transcripts, unrelated session history, secrets,
or broad project summaries.

## Acceptance Criteria

- [ ] Observable behavior:
- [ ] Regression safety:
- [ ] Scope safety:
- [ ] Verification evidence:

## Required Execution Receipt

The implementer must return a receipt using:

```text
harness-engine/.dev-harness/templates/execution-receipt-template.md
```

The receipt is evidence, not authority. The reviewer must compare it with the
actual diff and checks.

## Documentation Placement

- New `.dev-harness` markdown files follow `docs/document-governance.md`.
- Task-scoped notes go under `task-briefs/`.
- Review and audit outputs go under `reviews/`.
- Stable harness rules go under `docs/` unless they are one of the approved root manuals.
- Project strategy documents go under repository-level `docs/`, not `.dev-harness`.

## Tool Budget

- Allowed tools:
- Disallowed tools:
- External network needed: yes/no
- OpenAI API calls needed: yes/no
- Token budget (if OpenAI):

## Architecture Checks

- ����Ƿ񱣳�����ȷ�Ĳ㼶��
- �Ƿ񱣳ֺ���������Ϊ��ģ/Ԥ��Ȩ����
- �Ƿ����δ����׼�޸� L3 ����
- �Ƿ���ʧ�ܽ���Ϳ�����ԣ�
- �Ƿ�����ڱ��ػ��ƹ���ǰ����ƽ̨���Ӷȣ�
- �Ƿ񱣳ֲ�������Ϳ��� harness ���룿
- OpenAI API �����Ƿ���ѭ `docs/policies/openai-policy.md`��

## Verification

�������

```powershell
harness-engine/.dev-harness/checks/dev-gate.ps1
```

## Eval Criteria

- Task success:
- Regression safety:
- Architecture safety:
- Memory update:

## Stop Conditions

ʲô���Ӧ���� agent ͣ����ѯ���û���

- Required changes exceed allowed files or operations.
- Existing verification fails before implementation.
- Acceptance criteria are not observable.
- A secret, credential, or production data exposure would be needed.
- The implementer needs to change architecture, strategy rules, or data
  integrity assumptions.

## Rollback

��֤ʧ��ʱ��γ��������

## Write Task Acceptance Audit Addendum

WRITE_TASK_ACCEPTANCE_AUDIT

Every brief created by `写task` must perform rigorous acceptance before writing the next task.

Add these fields to `Previous Task Acceptance` when creating a new task:

- Acceptance audit performed:
- Errors found:
- Error-fix tasks included in this brief:

If the acceptance audit finds an error in the previous task, current harness state, evidence, review, gate, numbering, scope, or verification, the new brief must include fixing or explicitly blocking on that error as part of its task scope. Do not write a clean follow-on task while leaving known acceptance errors outside the scope.

## Task Stream Acceptance Addendum

Task Stream is required for every new task brief. Use a stable, narrow value such as `harness-write-task-governance`, `harness-memory`, `structure-proof`, or `event-library`.

`Previous Task Acceptance` applies only to the latest completed or blocked task in the same stream. Do not block a harness-governance task because an unrelated structure-proof or business task is still `CLAIMED`, and do not use a business task as the predecessor for a harness task unless the new task explicitly depends on it.

Add this field near the top of every new task brief:

- Task Stream:

Add this field to `Previous Task Acceptance`:

- Same-stream previous task:

If no same-stream previous task exists, state `none - first task in this stream` and explain why cross-stream tasks are not predecessors.
