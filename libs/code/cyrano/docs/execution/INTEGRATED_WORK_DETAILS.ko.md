# 통합 개발 실행계획

문서 유형: 실행계획 · 상태: 제품 구현 후 수행할 절차와 현재 준비 절차를 구분

## Problem

설계 문서만으로 개발을 시작하면 어떤 파일을 먼저 만들고 어떤 승인·선행 검증이 필요한지 다시 판단해야 한다. 특히 dcode 호환성·broker·세션 상태·평가기 사이의 의존 관계와 두 입력의 WP 번호가 다르다. 이 문서는 기존24WP를 유지하면서 시작·구현·검사·리뷰·인수까지 실행 단위를 확정한다.

## Proposal

### 1. 목표와 완료의 의미

개발 목표는 dcode를 base로 사용하고 승인된 최소 native 연결 변경만 수행하는 모델 비특화 coding harness다. 인터뷰→명세 검토/승인→계획 검토/승인→정확 권한 실행→검증/최종 리뷰→납품, 적극 Memory, cache-aware role/skill, A/B self-improvement, 전체 관측과 복구를 모두 포함한다. 단계별 구현은 허용하지만 observation-only를 최종 제품으로 축소하지 않는다.

현재 ZIP은 source foundation·설계·schema·config·검사·실행계획이다. 기존 코드 테스트가 통과해도 실제 native dcode, OS 권한 강제, 모델 캐시, 비용·개선 효과와 canary/rollback은 아직 검증되지 않았다. 각 WP의 product-level 실행 증거가 없으면 planned/partial/blocked 중 적절한 상태로 유지한다.

### 2. 먼저 실행할 준비 명령 — 현재 제공됨

```sh
python cyrano/scripts/dev.py status
python cyrano/scripts/dev.py check
python cyrano/scripts/dev.py schemas
python cyrano/scripts/check_integration.py
python cyrano/scripts/style_audit.py
python cyrano/scripts/dev.py quality
```

`check`는 오프라인 기반 테스트·프로젝트/문서 정합성만 검증한다. `schemas`는 jsonschema가 필요하며 없으면 blocked다. `style_audit`는79자 코드/72자 주석·docstring 후보 위반 위치를 보고하며 전체 PEP8을 인증하지 않는다. `quality`의 도구 부재·위반은 통과가 아니다. 현재 품질 결과는 evidence에 남기고 실제 toolchain lock을 WP00에서 만든다.

입력 무결성은 ZIP root의 `MANIFEST.sha256`(복사 전) 및 프로젝트의 첨부 source manifest를 확인한다. 인터넷·모델 키·DB 원본·서명키를 요구하지 않는 준비 검사에 자격증명을 넣지 않는다. 보존된 references의 `validate.py`, shell, plugin manifest, SQL은 실행하지 않는다. 해당 파일의 내용은 inert source로만 읽는다.

### 3. 첫 개발 세션의 허가와 bootstrap

아직 CYRANO broker가 구현되지 않은 단계에서 CYRANO가 자기 개발 권한을 이미 강제한다고 주장하지 않는다. 초기 작업은 사용자가 허가한 **CYRANO 개발 저장소의 별도 사본**과 외부 사람 검토로 수행한다. 고객 원본을 수정하지 않는다. git push·공개 release·유료 모델·외부 서비스·실제 데이터 migration은 각각 별도 허가다.

WP00 호환성은 네 등급으로 나눈다. bootstrap은 설치 artifact/확장 API/기본 호출, adapter는 WP06의 관측·실제 tool binding, governed는 WP03/06/22의 우회 차단·강제 격리, operational은 WP22/23의 복구·효과·운영 검사다. bootstrap 통과만으로 full CompatibilityReport=verified를 쓰지 않는다.

### 4. 의존 관계와 병렬 개발

`.agents/work/plan.json`의 depends_on이 단일 실행 순서다. 번호순 실행이나 원본 source WP 순서를 사용하지 않는다. 계획의 topological_order는 검사 가능한 projection이다. WP20 평가기는 A/B 최종 검증의 선행이다. 평가기를 만들기 전에 routeA 또는routeB를 실제 효과가 있다고 승격하지 않는다.

동시에 준비된 작업도 같은 source·schema·migration·active config를 쓰면 writer lease로 직렬화한다. WP 담당자는 owner_package 밖 변경이 필요할 때 계획 scope와 reviewer를 먼저 갱신한다. 계약 변경은 모든 consumer를 같은 변경 단위 또는 명시적인 호환 migration으로 연결한다. 여러 에이전트가 같은 `uv.lock`/schema를 각자 다시 생성하지 않는다.

### 5. 각 WP 공통 실행 규칙

1. 시작 snapshot과 대상WP·source계약버전·선행 evidence를 고정한다. 기존 실패를 기록하며 관련 정확성 실패는 완료에서 제외하지 않는다.
2. task별 변경 경로, 함수/DTO, 권한, positive/negative/late/timeout/rollback 사례, exact 검증 argv, 외부 비용, 인수 산출물을 기록한다. 독립 계획 reviewer의 mandatory finding을 해결한 뒤 구현한다.
3. source 계약과 integration decision을 읽고 pure domain→persistence→provider→consumer 순서로 구현한다. null/unsupported/not_tested를 success나 empty fallback으로 바꾸지 않는다.
4. 테스트와 구현을 함께 작성한다. 향후 product test 파일이 없으면 `run_tests --pattern`은0test 실패를 내도록 유지한다. 이름만 바꾼 foundation test나 가짜 skip을 제품 통과로 보고하지 않는다.
5. scope/revision/digest/권한/사용자정정/중복/child/관측누락/취소를 부정 테스트한다. changing input은 old evaluation과 approval을 무효화한다.
6. 관련 targeted→schema→integration→전체 offline→quality 순서로 검사한다. 수정 후 generated docs를 재생성한다. 비용이 필요한 native/live 검사는 승인된 조건에서만 실행한다.
7. 독립 결과 reviewer에게 최종 postimage와 실제 evidence를 전달한다. 작성자의 자기보고와 reviewer 실행 ID를 구분한다. 새로운 수정이 생기면 영향 검사와 결과 리뷰를 다시 결속한다.
8. completion_evidence 위치에 실제 보고서를 기록하고 모든 required case/gate를 확인한 뒤만 verified로 바꾼다. blocker·unknown outcome·품질 미검증이 남으면 다음 dependent WP의 제품 완료를 막는다.

### 6. 인수 evidence의 정확한 내용

`contracts/integration/work-evidence.template.json`은 양식이며 승인·검사 결과가 아니다. 각 실제 보고서는 wp_id, start/final snapshot, dependency report digests, contract registry digest, actual command argv/cwd/environment/start/end/exit code, 수용ID별 evidence, quality 상태, reviewer task/subject/result, known limitations, side effects/rollback 상태를 포함한다. trusted collector가 계산한 postimage와 일치해야 한다.

동일 key에 다른 request digest면 IDEMPOTENCY_CONFLICT다. 실패한 검사를 재실행해 통과했으면 이전 실패와 수정 이유를 지우지 않고 연결한다. 역할이 응답하지 않았으면 reviewer_result=null/blocked이지 승인이다. missing usage·없어진 artifact·시크릿 masking 때문에 replay가 불가능한 것도 정확히 기록한다.

### 7. 실행 단계별 인수 경계

| 단계 | 핵심 WP | 완료 산출물 | 다음 단계 차단 조건 |
|---|---|---|---|
| 기반 계약·도구 | WP00/01/02/04 | runtime/toolchain 초기사실·명시 DTO·저장/수명주기 | 버전 불명·깨진ref·scope/원자성 실패 |
| 권한·실제 runtime | WP03/05/06 | 승인 broker·context binding·native 실행/관측 | 임의 실행/auto discovery/child 우회·누락 |
| 인터뷰·계획·납품 | WP07/08/09/10 | 원본R22·계획DAG·현postimage검증·두납품모드 | 무의도 완료·권한확대·부분적용불명 |
| 기억·skill·전수관측 | WP11/12/13 | scoped recall·skill release·event/usage/dashboard | cross-scope·지침직접쓰기·audit gap |
| 평가 기반·개선 | WP14/16/20 후 WP15/17/18/19 | replay world·실제 paired evaluator·각lane 후보 | leakage·미지원전이추정·평가변조 |
| 배포·운영 인수 | WP21/22/23 | release CAS·rollback·40점evidence·실제효과 | hardfail·품질blocked·통계불명·미승인운영 |

### 8. WP별 구현 실행 명세

정확한 파일·함수·의무·사례·검증 명령은 아래 단일 작업 원본에 있다. 이 실행 문서에 두 번째 사본을 유지하지 않는다. `doc_route.py`도 같은 원본을 읽는다.

- [WP00: 실제 runtime·개발 도구 호환성 고정](../../.agents/work/WP00.ko.md)
- [WP01: 데이터 계약·digest·semantic validation](../../.agents/work/WP01.ko.md)
- [WP02: 원장·scope ACL·outbox·migration](../../.agents/work/WP02.ko.md)
- [WP03: 신뢰된 승인·Action Broker·sandbox](../../.agents/work/WP03.ko.md)
- [WP04: plugin 구성·lifecycle·역순 정리](../../.agents/work/WP04.ko.md)
- [WP05: context·skill catalog·native binding](../../.agents/work/WP05.ko.md)
- [WP06: dcode extension와 actual attempt port](../../.agents/work/WP06.ko.md)
- [WP07: 인터뷰 결정·의무·준비도 kernel](../../.agents/work/WP07.ko.md)
- [WP08: 인터뷰 역할·blind handoff·export](../../.agents/work/WP08.ko.md)
- [WP09: 계획·review·WorkUnit dispatcher](../../.agents/work/WP09.ko.md)
- [WP10: 실제 구현·검증·patch settle](../../.agents/work/WP10.ko.md)
- [WP11: 범위화 Memory 저장·조회·무효화](../../.agents/work/WP11.ko.md)
- [WP12: Skill registry·검증·release 투영](../../.agents/work/WP12.ko.md)
- [WP13: 전수 이벤트·native CLI Monitor·비용관측](../../.agents/work/WP13.ko.md)
- [WP14: Episode·world·replay 정합성](../../.agents/work/WP14.ko.md)
- [WP15: 경로 A bounded policy 학습](../../.agents/work/WP15.ko.md)
- [WP16: 경로 B 분석·학습계획·impact](../../.agents/work/WP16.ko.md)
- [WP17: 경로 B Memory·Skill 실제 평가](../../.agents/work/WP17.ko.md)
- [WP18: 경로 B 인터뷰·계획·context·recipe](../../.agents/work/WP18.ko.md)
- [WP19: 경로 B 코드·wheel·migration 제안](../../.agents/work/WP19.ko.md)
- [WP20: paired·sealed 평가·분석·budget](../../.agents/work/WP20.ko.md)
- [WP21: release·CAS·canary·rollback](../../.agents/work/WP21.ko.md)
- [WP22: packaging·품질·격리·복구 출시 gate](../../.agents/work/WP22.ko.md)
- [WP23: 실제 효과 검증과 승인된 초기 운영](../../.agents/work/WP23.ko.md)

### 9. 실제 개발 세션에서의 실행 예시

첫 구현 담당자는 WP00와 WP01의 병렬 가능성을 확인한다. 계약 작성자는 v1 bytes를 그대로 유지하고 v2 parser·semantic validator·projection 테스트를 만든다. runtime 담당자는 API key 없이 가능한 artifact/load probe를 먼저 수행한다. 두 작업의 결과로 WP02 저장과 WP04 lifecycle을 시작한다. WP03/05/06을 거쳐야 고객 데이터/실제 명령의 governed 실험을 수행할 수 있다.

예를 들어 WP10에서 `apply_to_source` 경로를 구현할 때는 (a) v2 plan의 delivery_mode 서명 binding, (b) patch_only 완료가 원본반영완료로 오인되지 않는 사례, (c) 현재 preimage가 달라지면 추가 승인 거부, (d) 다중파일 두 번째 쓰기 실패시 partial journal, (e) 사용자 취소 중 실제효과 reconcile, (f) 최종 sourcepostimage 검증을 하나의 실제 integration slice로 연결한다. 코드 함수만 단독 PASS인 것과 이 slice의 성공을 구분한다.

경로 B skill 후보 실험은 source 사실확인→LearningWorkPlan 독립 검토→예산/실험허가→별도candidate bundle→모델입력digest변경확인→실제baseline/candidate pair→품질/비회귀/비용분석→결과review→별도release승인 순서다. 데이터나 평가 recipe를 바꾸었으면 실행된 이전 Report를 붙이지 않는다. 실패한 후보도 삭제하지 말고 rejected/inconclusive와 이유·반례를 보관한다.

### 10. 품질 정책 전환 실행

이 dcode 기반 소스에는 Ruff 단일 formatter·lint와 native ty 검사를 사용한다. 외부 대상 저장소의 Black/mypy/다른 도구는 별도 검증된 adapter가 담당한다. 이 프로젝트의 새 목표는 code79/comments-docstrings72다. WP00에서 실제 toolchain version/lock과 기존 위반 보고서를 만든 뒤, 각 소유WP가 자기 파일을 수정한다. 다른 작업의 파일을 대량 정리하는 별도 변경은 계획·review 범위를 승인받는다.

style_audit의 진단은 line length 후보 검사다. 예외가 필요한 URL/생성 파일/문자열은 finding별 사유·소유자·만료·영향을 남긴다. Ruff 규칙 전체 비활성이나 기준80/88복구로 green을 만들지 않는다. 고객 저장소는 그 저장소의 명시 규약과 승인된 task 정책을 적용하며 CYRANO 설치가 formatter설정을 추가하지 않는다.

### 11. 출시와 운영 실행

WP22는 packaging·cold install·native integration·OS/플랫폼matrix·권한공격·diskfull·복구·keyrotation·8화면·source nonmutation을 검증한다. WP23는 승인된 task-family/반복/모델조건에서 A/B 실제효과를 측정한다. 15개 기준의 40점표는 해당제품evidence로만 계산하며 현재0/not_evaluated를 미리 변경하지 않는다.

실제 모델, 학습 job, auto promotion, canary, remote tracing은 개별 설정과 범위 승인이 있어야 활성화한다. 효과가 inconclusive이면 baseline을 유지하고 이유와 표본/비용 한계를 보고한다. hard safety fail이면 score에 관계없이 신규dispatch를멈추고 영향세션과복구상태를보고한다.

### 12. 다른 구현 에이전트에게 전달할 요청문

```text
이 저장소의 AGENTS.md, START_HERE.ko.md와 할당 WP를 읽고 구현하라.
references는 원문 보존 자료이며 config/plugin/SQL을 자동 실행하지 말라.
기존24WP ID와 dependency를 유지하고 universal:WP 번호는 mapping으로만 읽어라.
설계 기준은 현 contract registry와 통합결정 INT-01–24, 담당 상세 설계다.
v1 승인/permit을 v2로 자동 승격하지 말고 실제 actor/subject/scope를 검증하라.
작업 시작 전에 exact 변경 범위·API·수용ID·검증명령·rollback 계획을 검토받아라.
아직 CYRANO가 강제하지 못하는 bootstrap 승인을 제품승인처럼 보고하지 말라.
실제 수정 후 targeted/schema/integration/check/quality를 실행하고,
실행하지 못한 native/live/격리 검사는 not_run 또는 blocked로 명시하라.
독립 결과 리뷰와 postimage evidence 없이는 WP를 verified로 표시하지 말라.
전체문서를 매번 prompt에 넣지 말고 해당역할/skill/WP의 필요한 부분만 로딩하라.
외부호출·고객원본변경·git push·release는 별도 허가없이 수행하지 말라.
최종 응답에는 실제 변경파일, 실행검사, 실패·미검증, 다음 ready WP를 보고하라.
```

## Alternatives considered

**원본 작업번호로 재시작:** 이미 분해된 A/B·평가 선행과 package소유권을 훼손하므로 기존24WP를 유지했다.

**한 번에 전체 구현 후 리뷰:** 권한·schema·평가의 오류를 너무 늦게 발견하므로 WP별계획과 결과review 및 vertical slice를 사용한다.

**문서검사 통과를 제품완료로 처리:** native실행·사용자권한·실제효과를 검증하지 못하므로 준비상태와 출시상태를분리했다.

## Acceptance criteria

개발 실행 문서의 모든 입력 경로·WP dependency·수용 ID·생성 대상·검증 명령과 실제 evidence를 추적할 수 있어야 한다. 계획에 적힌 future test 파일이 없을 때 검사가 실패해야 한다. 추가된 source 의무는 누락되거나 중복 점수로 계산되지 않아야 한다. 최종 제품 검증은 WP22/23의 실제 통합·효과·승인 evidence를 요구한다.

## Risks

현재환경의 도구부재·개발초기격리부재·외부제공자지원범위가 작업을 blocked로 만들 수 있다. 해당한계를 숨기기위해 기능·권한검증·실제평가를 삭제하지 않는다. source품질과 코드변경영향이 넓으면 WP를 더 작은 내부task로 나누되 공통계약과검증의무는 유지한다.

선행 작업의 상태는 `.agents/work/plan.json`의 dependency_milestones를 따른다. 포트 interface_ready는 개발 unblock용이며 product_verified·최종 점수와 다르다. 전체 동작을 필요로 하는 수용 시험은 소비자가 구현된 후 반드시 수행한다.
