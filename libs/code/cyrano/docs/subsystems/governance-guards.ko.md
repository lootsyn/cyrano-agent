# 세션 전이 guard 구현 명세

문서 종류: 목표 reference. 현재 candidate transition foundation과 다른 session 서비스이며 아직 구현되지 않았다. 소유 WP07, 승인 guard WP03, 실행/완료 guard WP09–10, runtime gate WP06.

## 인터페이스

`SessionService.handle(command, authenticated_context) -> CommandReceipt`는 외부 진입점이다. 내부 `resolve_transition(snapshot, event) -> TransitionSpec`은 catalog에서 유일한 전이를 선택한다. `evaluate_guard(spec, trusted_repositories) -> GuardDecision`은 현재 artifact를 읽고 결과를 계산한다. GuardDecision은 passed·blocker_codes·evidence_refs·evaluated_bindings를 가지지만 외부 모델이 제출하는 DTO가 아니다.

state/event/outbox를 같은 transaction에서 저장한다. 오래 걸리는 외부 실행을 DB transaction 안에서 기다리지 않고 operation journal+outbox로 분리한다. 마지막 CAS 시점에 guard 입력의 revision/binding이 그대로인지 다시 검사한다. 바뀌면 STALE_REVISION으로 결과를 버리고 새 상태에서 재평가한다.

## 정확한 guard 목록

| guard | 신뢰 저장소 입력 | 필수 판정 알고리즘 | 대표 차단 코드 |
|---|---|---|---|
| `workspace_runtime_policy_bound` | WorkspaceIdentity+RuntimeLock+policy revision+scope ACL | workspace canonical root/digest와 runtime/policy binding이 신뢰 저장소와 일치; bootstrap에서는 해당 probe 단계만 인정 | `WORKSPACE_BINDING_MISMATCH` |
| `trusted_input_and_memory_view_ready` | TrustedUserEvent+current intent ledger+authorized MemoryAccessBinding | 입력 actor·수신 이벤트와 session 연결을 검증; memory view가 없는 경우 명시 empty-view를 결속하며 타 scope 결과를 섞지 않음 | `UNTRUSTED_USER_INPUT` |
| `read_scope_available` | resolved permission_set+requested evidence paths | 정확 read grant와 deny를 적용; 읽을 수 없는 의무는 질문 또는 scope 요청으로 남김 | `READ_SCOPE_DENIED` |
| `no_redundant_question` | current decision ledger+question candidate+open obligations | 이미 답한 동일 의무를 재질문하지 않음; 요구 변경/충돌/새 근거이면 이유와 supersedes를 기록 | `REDUNDANT_QUESTION` |
| `no_unresolved_mandatory_obligation` | canonical obligation graph+readiness report | 모든 mandatory 의무의 결정/근거/승인 상태 유효; 점수나 낮은 모호도로 blocker 상쇄 금지 | `UNRESOLVED_BLOCKER` |
| `evidence_snapshot_provenance_valid` | evidence artifact+snapshot+scope+source locator | 원문 hash/존재/유효성/ACL 검사; 삭제/만료/다른 snapshot 근거는 false 또는 unavailable | `STALE_EVIDENCE` |
| `read_or_probe_authorized` | read grant+probe recipe+permit+runtime binding | 단순 read와 실행 probe를 구분; 테스트/import/build는 실행 허가와 recipe 필요 | `PROBE_NOT_AUTHORIZED` |
| `trusted_user_event_not_model_report` | host ingress authentication+event id+raw text digest | 모델 tool body가 아니라 인증된 사용자 수신 사건을 원장에 결속; 원문 보존 정책 적용 | `UNTRUSTED_USER_EVENT` |
| `bundle_strict_and_content_addressed` | strict InterviewContract+artifact refs | schema와 dangling/crossscope refs 검사 후 CYRANO-C14N-1 subject를 계산; 후보가 준 digest를 독립 재계산 | `INVALID_BUNDLE` |
| `finding_targets_current_digest` | WorkerOutcome+AgentTask+current spec digest | worker task/revision/input/role/subject 일치; stale 결과의 새 반증은 별도 evidence 후보로 보존 | `STALE_REVIEW` |
| `required_current_independent_reviews_and_no_blockers` | ResolvedTaskProfile+spec reviews+finding dispositions | critic/blind 및 해당security review가 현재 subject에 결속되고 mandatory finding 미해결0; 자기 review 금지 | `SPEC_REVIEW_REQUIRED` |
| `trusted_exact_approve_spec_for_planning` | TrustedApprovalReceipt+spec digest+display event | action approve_spec_for_planning과 정확 binding·actor·nonce·기간·철회 검사; 실행권한으로 사용불가 | `APPROVAL_PURPOSE_MISMATCH` |
| `spec_approval_current` | spec approval+current obligation/contract subject | 정정·철회로 무효화되지 않은 승인과 exact spec 참조를 확인 | `STALE_SPEC_APPROVAL` |
| `dag_scope_traceability_verification_budget_valid` | GovernedWorkPlan+exact permissions+recipes+budget ledger | cycle/dangling/동시writer/requirement누락/create/write/delete혼동 검사; 모든필수검사와 rollback 및 보수예산 존재 | `INVALID_PLAN` |
| `current_plan_findings` | plan review task+current plan subject | 현재 plan digest에 대한 finding만 상태를 변경; stale review는 적용하지 않음 | `STALE_PLAN_FINDINGS` |
| `independent_current_plan_review_no_blockers` | profile+planreview+findingdisposition | 작성자와 분리된 plan-reviewer 실행·현재 digest·필수 finding 해결을 확인 | `PLAN_REVIEW_REQUIRED` |
| `trusted_exact_approve_plan` | receipt+plan subject+display | action approve_plan 검증; delivery_mode·exactpaths·budget 변경시 다시승인 | `PLAN_APPROVAL_INVALID` |
| `display_exact_files_recipes_budget` | current plan+trusted display event | 사용자가 본 정확한 파일 작업/recipe/예산/납품모드 문서 digest를 기록; 숨은 확대없음 | `APPROVAL_DISPLAY_MISSING` |
| `trusted_authorize_execution_scope_intersection` | authorize_execution receipt+parent approvals+resolved profile | 명세/계획승인과 실행허가를 분리; scope교집합/deny우선/예산min 및 currentepoch 적용 | `EXECUTION_NOT_AUTHORIZED` |
| `governed_adapter_audit_budget_preimage_valid` | governed CompatibilityProbes+permit+reservation+preimage | 모든필수연결verified, audit healthy, lease/fencecurrent, budgetreserved, preimagecurrent일때만dispatch | `EXECUTION_PREFLIGHT_FAILED` |
| `observed_changes_no_unknown_side_effects` | trusted change manifest+operation journal+workerresult | actual changedfiles가허가범위이고 실행중/unknown목록없음; 모델요약만으로검증단계진행금지 | `UNKNOWN_EXECUTION_OUTCOME` |
| `same_scope_repair_possible` | failed verification+current grant+remainingbudget | 필수기준변경없이 동일scope/postimage수정계획가능; 범위확대는plan review로복귀 | `REPLAN_REQUIRED` |
| `repair_within_current_contract_possible` | verificationfailure+currentrequirement+failurekind | 환경오류/TDDred/제품오류 분리; 요구변경은CHANGE_ASSESSMENT, 동작수정은boundedrepair | `CONTRACT_REVIEW_REQUIRED` |
| `current_postimage_all_required_evidence` | all RunnerVerification+current changes+requiredchecks | 동일postimage/run/recipe/schema에 결속; 필수test0/allskip/미실행/unknown없음; 해당비테스트check는test_count_applicable=false | `VERIFICATION_EVIDENCE_MISSING` |
| `current_findings_within_approved_scope` | finalreview+currentartifact+affectedpaths | finding이현재postimage를지목하고수정scope유지; 기준약화나신규기능이면재계획 | `REWORK_SCOPE_MISMATCH` |
| `existing_or_new_permit_current_and_scope_unchanged` | repairplan+permit+approval+budget | 남은횟수/기간/epoch/preimage를재검증; 만료permit자동연장금지 | `PERMIT_EXPIRED_OR_STALE` |
| `delivery_patch_only_and_all_completion_gates` | plan.delivery_mode+finalreviews+verification+patchdeliveryreceipt | patch_only이며현재manifest 전달확인, blocker/requiredgap/unknown0; 원본반영을완료했다고표시금지 | `DELIVERY_NOT_COMPLETE` |
| `delivery_apply_to_source_and_all_patch_checks` | delivery_mode+stagedchanges+finalreview | apply_to_source이며검증된patch와현재sourcepreimage범위를표시할준비완료; 아직완료아님 | `APPLY_APPROVAL_REQUIRED` |
| `trusted_authorize_apply_patch_and_source_preimage_current` | apply receipt+current source fingerprint+journal | authorize_apply_patch와정확patch/sourcepreimage 검증후writerlock 획득; 사용자외부수정이면새승인 | `SOURCE_PREIMAGE_CHANGED` |
| `source_manifest_and_required_final_checks_passed` | apply journal+actual sourcepostimage+finalchecks | 모든허가파일의실제사후hash와필수검사가일치; 부분적용/미결작업없음 | `SOURCE_APPLY_INCOMPLETE` |
| `durable_journal_exists_or_gap_explicit` | operationjournal+observedfilesystem+gaprecord | journal있으면 actual state기록; journal손실은gap과영향범위불명으로명시, 성공추정금지 | `RECONCILIATION_REQUIRED` |
| `actual_partial_state_and_recovery_next_action_recorded` | reconcile report+source snapshot+next action proposal | 적용/미적용/unknown 파일을분류하고복구계획기록; BLOCKED에서자동재시도않음 | `RECOVERY_PLAN_MISSING` |
| `affected_entities_invalidated` | trustedintentchange+dependencygraph | 역의존BFS로affecteddecision/spec/plan/review/approval/permit/context를stale/revoked; 새revision원자저장 | `INVALIDATION_INCOMPLETE` |
| `spec_still_valid_and_plan_dependents_invalidated` | changeassessment+unchangedspecdigest+plangraph | spec유효성검사후 plan-only영향범위무효화; spec바뀌면FRAME | `SPEC_CHANGED` |
| `no_new_dispatch_and_all_running_ops_accounted_for` | cancel token+operationledger+budgetliabilities | 신규dispatch정지, 모든running작업settled/reconciled; unknown남으면CANCELLING | `CANCEL_PENDING_OPERATIONS` |
| `trusted_cancel_stop_new_dispatch_immediately` | trusted user cancel+runid | 인증된취소를원자기록하고runepoch/permits를철회; 실행중작업정리시작 | `UNTRUSTED_CANCEL` |
| `persist_resume_checkpoint_and_operation_status` | phasecheckpoint+runtimebinding+outstandingoperations | pause사유와안전resumecheckpoint저장; 실행미결을숨기지않음; 더큰권한복귀금지 | `CHECKPOINT_NOT_DURABLE` |
| `revoke_affected_permits_and_invalidate_dependents` | userchange/securityevent+dependencygraph | affected권한즉시철회, 신규dispatch정지, 무효화event/outbox를원자저장 | `REVOCATION_NOT_DURABLE` |

## pause·failure와 공통 오류

명시전이→해당 global전이 순서로 하나만 선택하며 겹치면 catalog오류다. unknown event는 INVALID_TRANSITION이다. PAUSED/BLOCKED의 resume는 caller target이 아니라 checkpoint를 읽어 current guard를 다시 평가한다. 중간 의미변경은 CHANGE_ASSESSMENT, 실제부작용불명은 RECONCILING으로 간다. terminal 상태에는 resume하지 않고 새 승인 세션을 만든다.

모든 guard에서 missing evidence, 서로 다른 scope, 유효하지 않은 서명, 삭제·만료 artifact, unknown runtime 상태는 성공이 아니다. 외부에 구체적인 blocker ID와 허용 가능한 다음 행동을 반환하되 비밀경로/본문을 유출하지 않는다. `guard_result=true`를 wire body에서 읽어 상태를 바꾸는 API는 제공하지 않는다.

## 구현 수용 조건

catalog의 모든 전이에 정상·차단·stale CAS 사례를 작성한다. 새로운 session_state.py는 기존 candidate transitions.py를 호출해 상태명을 매핑하지 않는다. guard 조합 테스트는 실제 저장소/승인 검증을 포함하는 product test와 pure reference test를 구분한다.

## 객체 간 의미 검증

아래 규칙은 JSON Schema만으로 구현되지 않는다. 각 서비스가 인증된 저장소·runner·현재 binding으로 추가 검증해야 한다. source schema fixture 통과를 이 검증의 성공으로 표시하지 않는다.

| ID | 대상 | 구현 WP | 정확한 검사 | 차단 코드 |
|---|---|---|---|---|
| GOV-SEM-01 | all external documents | WP01 | Reject duplicate keys, non-finite/float numeric values, unpaired surrogate, excess depth/bytes and unknown kind/version before digest. Money is nonnegative decimal text; integral budgets are bounded safe integers. | INVALID_SERIALIZATION |
| GOV-SEM-02 | GovernedWorkPlan | WP09 | Recompute exact subject. WorkUnit IDs are unique; dependency graph is acyclic; every required obligation/scenario maps to work plus required verification. Sum/reserve bounded cost without float; overlapping writers need serialization. | INVALID_PLAN_GRAPH |
| GOV-SEM-03 | PermissionSet | WP03 | Resolve authenticated root_id to tenant/user/workspace. Missing grant is empty. Effective grants are intersections, deny is union. Require fd-level root and alias protections. only_write must be disjoint from every readable mount/fd and uses artifact_write action; unsupported capability is rejected. | PERMISSION_BOUNDARY_UNAVAILABLE |
| GOV-SEM-04 | TrustedApprovalReceipt | WP03 | Verify issuer allowlist/signature over exact v2 projection, authenticated actor and display event, nonce consumption, expiry ordering/current time and revocation. Spec-for-planning, approve_plan, authorize_execution and authorize_apply_patch are distinct; a new display is required when subject or delivery changes. | INVALID_APPROVAL_BINDING |
| GOV-SEM-05 | ToolExecutionPermit | WP03 | Check all parent approvals current and action-compatible; effective scope/budget is a subset; compare policy epoch, fencing token, runtime/tool inventory, work unit, sandbox and preimage at dispatch. A worker never renews its own token. | INVALID_EXECUTION_CAPABILITY |
| GOV-SEM-06 | RunnerVerification | WP10 | Authenticate runner. Check run/work_unit/check/recipe/runtime/postimage match required verification spec. started_at<=finished_at. With applicable counts require nonnegative observed integers, passed+failed+skipped<=collected, collected>0 and passed>0 for final pass. Setup error, zero collected, all skipped and expected TDD red are not final pass. | INVALID_VERIFICATION_EVIDENCE |
| GOV-SEM-07 | ExecutionChangeManifest | WP10 | Observe each exact change from trusted runner. create requires absent before; delete absent after; modify present before/after. No duplicate or unexpected paths. Compare postimage and operation journal, never infer atomic whole-workspace apply. | CHANGE_MANIFEST_MISMATCH |
| GOV-SEM-08 | RunCompletionReport | WP10 | Recompute from current source and trusted evidence, not submitted claims. Every required check and reviewer binds the final subject/postimage; no unresolved blocker or mandatory coverage gap or unknown effect. apply_to_source additionally requires exact apply approval, completed journal and final actual-source checks. | FALSE_COMPLETION |
| GOV-SEM-09 | MemoryAccessBinding | WP11 | Apply full tenant/user/workspace plus optional session/task ACL before ranking. Verify memory, evidence, release and freshness; active preferences/procedures require relevant trusted approval. Deleted/revoked dependencies invalidate selected views and replay support. | MEMORY_BINDING_INVALID |
| GOV-SEM-10 | GovernedEvent | WP13 | Resolve payload_schema_ref from fixed event catalog, not caller path; verify payload discriminant and canonical redacted digest, producer identity and scope. event_seq allocated by DB; producer_seq deduped. Only listed semantic mutations may advance control_revision. | EVENT_AUTHORITY_MISMATCH |
| GOV-SEM-11 | model/tool/budget event payloads | WP13 | Record observed statuses, not event-name inference alone. Nullable usage is unknown, not zero; measured requires usable semantics. Parent spans are not billable leaves. Reconcile actual charges and keep unknown reservation liability before allowing new billable work. | USAGE_ACCOUNTING_INCOMPLETE |
| GOV-SEM-12 | LearningTriggerObservation | WP16 | Classify expected red, correct denial, environment issue and requirements change separately. Read evidence from current terminal event. Deduplicate run/terminal/policy job identity and bound meta depth; a failed job cannot rewrite completed user-work outcome. | INVALID_LEARNING_SIGNAL |
| GOV-SEM-13 | CandidateProposal/EvaluationReport | WP20 | Impact classification comes from reviewed diff. All B and final A require actual current paired evidence. Check candidate/baseline/dataset/runtime/model/endpoint/budget bindings and project-family/time split. Changing any measured subject invalidates the old evaluation. | STALE_OR_LEAKED_EVALUATION |
| GOV-SEM-14 | ResolvedTaskProfile | WP05 | Intersect permissions, union mandatory checks/reviews, minimum budgets with explicit currency; no missing default broadening. Map legacy standard risk only at validated version adapter; model identity never branches role instructions. Recompute profile digest excluding own hash. | PROFILE_RESOLUTION_INVALID |
| GOV-SEM-15 | CompatibilityProbe | WP06 | verified requires actually executed evidence bound to exact installed artifact and host. Metadata-only probes cannot satisfy governed isolation, child interception or operational tests. All required stages must be verified for selected assurance; no silent downgrade. | COMPATIBILITY_NOT_VERIFIED |
| GOV-SEM-16 | session lifecycle | WP07 | Resolve resume from saved checkpoint/current guards. User cancel stops new dispatch; unknown existing effects keep CANCELLING/RECONCILING. Material change revokes dependent authorization. Candidate lifecycle is a different aggregate. | INVALID_SESSION_TRANSITION |
| GOV-SEM-17 | source migration | WP02 | Preserve signed source bytes and historical events. Quarantine unresolved scope, do not assign global. Backup/dry-run/invariant/restore evidence and new approvals are required before write enable. target SQL syntax pass is not migration evidence. | MIGRATION_NOT_AUTHORIZED |
| GOV-SEM-18 | CommandEnvelope/work.settle | WP10 | Transport envelope v1 version is independent of explicit payload schema version. work.settle ingests a RunnerVerification for the current operation; it does not mark the whole WorkUnit complete. Trusted workflow service correlates all checks, change manifests and reviews before completion. | INCOMPLETE_WORK_SETTLEMENT |
