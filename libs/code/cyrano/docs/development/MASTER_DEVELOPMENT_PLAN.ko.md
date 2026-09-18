# 개발계획: 선행 관계·담당·산출물

문서 유형: 개발계획 · 상태: 계획(제품 미구현)


## Problem

전체 제품 명세를 한 번에 구현시키면 하위 모델이 중요한 권한·상태·평가 경계를 생략하거나 서로 다른 계약을 만들기 쉽다. 작은 단위의 완료와 전체 제품 완료를 구분하고 각 단계의 입력·출력·테스트를 고정해야 한다.

## Proposal

### 현재 통합 개발계획

기존 24개 WP의 소유권을 유지하되 현재 의존관계는 plan.json을 따른다. 연구 결과와 인터뷰 이후 심층 계획/리뷰/HITL 요구를 해당 WP의 구현 단위로 직접 통합했다. 실행 상세는 각 WP 문서를 읽는다.

자세한 해석·충돌 해결은 [Universal Harness 통합 설계](../design/architecture/2026-09-16-universal-harness-integration.ko.md)를 따른다. 원본첨부에 있는 더 느슨한예시로 이규칙을낮추지 않는다.

### 1. 작업 원본과 상태

작업 원본은 `.agents/work/plan.json`과 같은 ID의 `.agents/work/WPxx.ko.md`다. 이는 기능별 소유권을 가진 개발 작업 DAG다. 현재 설계와 실행 조건을 참조하며 납품 버전 이력과 분리한다. product plan source와 runtime user PlanBundle은 다른 객체다.

모든 WP는 planned로 시작한다. foundation_present는 기존 순수 함수·테스트가 있다는 뜻이며 verified가 아니다. 진행 상태 planned/in_progress/in_review와 검증 단계 interface_ready/product_verified를 구분하고 blocked/needs_rework를 별도로 기록한다. 최종 verified는 product_verified 의무를 충족한 상태다. 선언만으로 상태를 바꾸지 않고 completion evidence를 요구한다.

### 2. 작업 DAG

정확한 의존관계는 `.agents/work/plan.json`을 읽는다. [통합 개발계획](R5_MASTER_PLAN.ko.md)은 포트 준비/제품 검증의 분리와 병렬 개발 원칙을 설명한다. 문서의 중복 DAG 표를 수동으로 유지하지 않는다.

번호는 주제 분류 순서다. WP20은 WP15/17/18/19보다 먼저 실행해야 하며 숫자 순서대로 수행하면 안 된다. machine topological_order가 기본 순서를 제공한다. 읽기 전용 설계 검토는 병렬 가능하지만 같은 package·contract를 쓰는 작업은 coordinator가 lock·ownership으로 직렬화한다.

### 3. 단계별 목표

Foundation 강화는 WP00–04에서 실제 runtime 가능성·타입·원장·승인·구성을 확정한다. 업무 수명주기는 WP05–13에서 context·dcode·interview·plan·actual code·memory·skills·관측을 연결한다. 개선 엔진은 WP14/16과 WP20을 만든 뒤 A와 B의 표면별 evaluator를 연결한다. WP21–23은 release·통합/보안·실제 효과를 검증한다.

최종 기능은 모든 WP를 포함한다. 처음 observation-only로 검증하더라도 후보 생성·실제 평가·승인·배포·rollback을 backlog에서 삭제하지 않는다. 고객 데이터나 paid API 권한이 없어 마지막 실험을 못 하면 implementation complete와 effectiveness not_verified를 따로 보고한다.

### 4. 코딩 기준

Python>=3.12를 목표로 한다. Ruff formatter 79열은 프로젝트 스타일 선택이며 PEP8의 모든 항목을 자동 증명하지 않는다. Ruff E/F/I/B/UP, native ty 검사, public module/class/function docstrings, explicit errors, immutable value types, UTC aware timestamps, 금액 decimal 표현, no silent fallback을 사용한다. 네트워크·DB·filesystem 자원은 context/lifecycle로 닫는다.

새 dependency는 기존 코드를 실제로 줄이는지, 라이선스/보안/업데이트 비용을 검토한다. 모든 import를 mock으로 우회한 테스트만 만들지 않는다. packages는 공개 import로 연결하고 source와 built wheel 모두 테스트한다. libs/code/uv.lock은 원본 dcode resolver 산출물이다. 이번 추가분에는 별도 runtime lock을 가짜로 생성하지 않으며 실제 환경·품질 도구의 고정은 WP00에서 수행한다.

### 5. 테스트 전략

작은 unit, 실제 DB·port integration, native dcode integration, OS isolation, paid actual eval을 구분한다. 수용 catalog는 원본 interview22·DREAM56·새 추가 회귀를 보존한다. CI에 없는 테스트를 로컬 PASS라고 기록하지 않는다. fixture/replay 테스트는 no-key로 돌아야 하며 live 테스트는 허가·예산·대상·key가 없으면 blocked/not_run으로 기록한다.

각 WP는 targeted tests를 먼저 실행하고 관련 integration·schema·docs·quality를 추가한다. production release CI는 필수 전체 matrix를 실행한다. 기존 통과 테스트를 unrelated commit 때문에 무한 반복하지 않으며 영향 범위와 기준 artifact를 기록한다.

### 6. Reviewer 권한

architect는 설계와 interface를 조정한다. implementer는 할당 경로만 수정한다. reviewer는 별도 입력으로 acceptance·diff·실행 evidence를 검토한다. security-reviewer는 auth·sandbox·secrets·release·judge 관련 변경을 필수 검토한다. release-reviewer는 전체 evidence와 배포·rollback을 검토한다. 어느 role도 prompt만으로 사용자 approval을 발급하지 않는다.

## Alternatives considered

**전체 monolithic 한 번 구현:** 누락과 review 범위가 커진다. contract를 먼저 고정하고 DAG로 진행한다.

**model별 팀 역할 고정:** 사용자가 제외한 특화다. 역할을 작업·위험으로 정하고 실제 배포 모델은 별도 운영 설정에서 선택한다.

## Acceptance criteria

24개 WP 모두 정확한 선행·소유·입출력·테스트·완료 evidence 경로를 가진다. DAG cycle과 dangling refs는 gate가 거부한다. 모든 제품 요구가 acceptance와 WP에 연결돼야 한다. 계획만 있는 항목은 verified가 될 수 없다.

## Risks

cross-package 인터페이스를 병렬로 바꾸면 재작업이 생긴다. shared contract owner와 변경 lock을 사용하고 위반 시 rebase·재평가한다. 운영 환경을 추정해 존재하지 않는 API를 구현하지 않는다.

## Native CLI 모니터링의 현재 설계 연결

사용자 운영 모니터링의 기본은 [dcode 내부 Monitor](../design/NATIVE_MONITOR_TUI.ko.md)다. 기존 dashboard 용어는 이 native 화면의 읽기 view를 포함하는 개념이며 외부 웹 UI 필수 요구가 아니다. 실행은 RF07–RF09에서 native 명령·인증 query·Textual·실제 호출 coverage를 함께 검증한다.
