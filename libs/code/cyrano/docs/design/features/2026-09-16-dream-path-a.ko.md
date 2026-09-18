# 경로 A: 지원 범위가 명시된 탐색 정책 개선

문서 유형: 상세 설계 · 상태: 계획(제품 미구현)


## Problem

과거 task 결과로 다음 branch 선택을 개선할 수 있지만, 전체 tree의 미래 점수를 정책이 읽거나 기록에 없는 시도를 실패로 넣으면 평가가 왜곡된다. 코딩 에이전트는 다른 branch의 결과·memory·사용자 correction을 읽기 때문에 Git parent만 같은 것으로 replay 입력 동일성을 보장할 수 없다.

## Proposal

### 통합 R2 관측과 replay 지원

typed payload와 sourceinput보존정책을따른다. 삭제/만료/비공개로원본input을회수할수없으면 exact replay unavailable이다. currentruntime/model/endpoint/부모외dependency가달라지면기록된결과를재사용하지않는다. 새session상태의stop/cancel이candidate성공이나업무완료를의미하지않는다.

자세한 해석·충돌 해결은 [Universal Harness 통합 설계](../architecture/2026-09-16-universal-harness-integration.ko.md)를 따른다. 원본첨부에 있는 더 느슨한예시로 이규칙을낮추지 않는다.

### 1. 유지할 연구 아이디어와 한계

DREAM의 핵심인 실행→정책 후보 탐색→기록 기반 평가→실제 탐색 반복을 활용한다. 전체 연구 구현이 공개·재현 검증되었다고 주장하지 않는다. 이 설계는 첨부 DREAM 명세를 프로젝트 구현 단위로 옮긴 것이며 연구 수치의 제품 재현을 약속하지 않는다. replay fidelity와 새 작업의 effectiveness를 분리한다. 기존 정책을 후보에 포함하면 해당 기록 점수의 비열등성을 선택할 수 있지만 미래 업무 개선을 보장하지는 않는다 [S10].

### 2. Episode와 전이 서명

Episode 시작 시 requirement/acceptance snapshot, source snapshot, dcode/runtime/dependency digest, model/provider/route, tool inventory, stable prompt, memory release, environment, evaluator, budget policy를 고정한다. 이것이 `input_signature`의 재료다. 관련 값이 바뀌면 새 episode 또는 B 평가가 필요하다.

기본 입력은 frozen common context + branch-local ancestry다. 다른 branch observation을 사용한 전이는 그 ID들을 `dependency_node_ids`로 명시한다. code genealogy와 information dependency를 모두 저장한다. 필요한 observation이 아직 공개되지 않았다면 과거 결과를 재사용할 수 없다.

### 3. 정책이 보는 정보

PolicyObservation은 현재 frontier의 공개 진행 지표, 과거에 관측한 오류 종류, 복구 가능 여부, 이미 사용한 시도 수, 남은 예산, 합법 action 목록이다. 미래 점수, 최종 best branch, 숨은 acceptance, 결과가 드러나는 ID, 원본 replay tape는 전달하지 않는다.

Policy Runner는 전체 tape를 mount하지 않는 별도 process/container에 둔다. Python 객체의 `_private` field만 숨기는 것은 테스트 구조이지 보안 경계가 아니다. future permutation test는 같은 공개 입력에서 숨은 미래만 바꿔도 다음 action이 같아야 한다. 정책 코드가 file/network/clock으로 결과를 읽을 수 없는지 실행 제한도 검사한다.

### 4. 행동과 barrier batch

합법 action은 `open_branch(slot)`, `continue_branch(frontier)`, `stop_exploration(reason)`다. executor는 승인·예산 안에서만 시도를 실행한다. 초기 구현은 barrier batches를 사용한다: 한 batch가 끝나기 전에는 batch 내부 일부 결과를 다음 정책 결정에 공개하지 않는다. 그래야 기록된 순서/의존성 의미가 명확하다.

batch의 action 중 하나라도 기록이 없거나 input signature가 다르면 batch 전체를 `out_of_support`로 표시하고 결과를 부분 공개하지 않는다. 지원되는 action만 실행한 것처럼 점수를 계산하면 불리한 부분이 사라진다. 미지원은 성능 실패가 아니며 새 sandbox 실행 예산이 있는지 검토하는 상태다.

### 5. Bounded policy IR

고정된 넓게/깊게 profile 몇 개를 고르는 기능으로 축소하지 않는다. 정책 후보는 허용 feature를 산술·비교·논리 연산으로 조합해 frontier 우선순위, 제한된 retry, branch 개방 조건, batch 크기, stop 조건을 정의할 수 있다.

IR은 recursion·임의 loop·eval/import·filesystem/network·동적 code loading이 없다. node 수, depth, numeric bound, 평가 시간·메모리, action count를 검증한다. 존재하지 않는 feature나 protected evaluator 값을 참조하면 거부한다. 더 복잡한 Python 정책은 code lane의 변경 제안과 별도 review를 필요로 한다.

### 6. Replay evaluator

`build_world(episodes)`는 완전한 transition bundle과 provenance를 만든다. `reset(signature)`는 고정 world를 선택한다. `observe()`는 공개 view만 반환한다. `step(batch)`는 합법성→signature→dependency visibility→support를 검사한 뒤 recorded results를 barrier로 공개한다. `score()`는 지원된 완결 실행에 대해서만 반환하며 미지원 world의 점수를 임의 보간하지 않는다.

지원 coverage, 미지원 원인, 평가에 사용한 world 목록을 보고한다. 후보에 유리하도록 불리한 world를 분모에서 제외하지 않는다. common supported subset 비교는 탐색용 진단으로만 명시하고 full task effectiveness 주장과 구별한다. historical 비용·latency는 proxy이며 새로운 scheduling의 실제 과금·시간과 동일하다고 하지 않는다.

### 7. 실제 탐색과 분기 병합

A 후보는 replay에서 선별한 뒤 actual baseline/candidate task 평가를 거친다. `stop_exploration`은 추가 탐색 중단일 뿐 전체 task complete가 아니다. 최종 acceptance·review·source apply approval은 별도다.

branch 산출물은 서로 격리된 snapshot이다. 선택하지 않은 patch를 main workspace에 부분 적용하지 않는다. 여러 branch를 합치는 경우 merge plan과 conflict 검증을 별도 WorkUnit으로 수행한다. 최종 테스트는 합쳐진 실제 artifact에서 실행한다. 독립 branch에서 각각 통과했다는 사실로 merge artifact를 통과 처리하지 않는다.

### 8. 실패와 비용

invalid action은 정책 실패, missing record는 out_of_support, environment failure는 관측 종류, cancellation은 취소다. 동일하게 0점 처리하지 않는다. 실제 호출에는 실행 permit, max attempts, deadline, monetary cap이 필요하다. external timeout 후 unknown outcome은 reconciliation 대상이다. retry count를 늘려 score를 얻되 actual total cost를 숨기는 정책은 효율 개선으로 보고하지 않는다.

## Alternatives considered

**전체 replay tree를 policy Python에 전달:** 구현은 단순하지만 미래 결과가 유출된다. 공개 observation projection과 격리 runner를 사용한다.

**기록 없는 행동을 실패로 평가:** 새로운 전략 탐색이 영구히 차단된다. out_of_support와 actual exploration을 분리한다.

**다른 branch 실패를 항상 공통 context에 합치기:** scheduling 변경이 모델 입력을 바꾼다. branch-local 기본값과 명시적 정보 dependency를 사용한다.

## Acceptance criteria

미래 permutation 불변성, signature mismatch 거부, dependency 미관측 거부, 부분 batch 비공개, 미지원 score 금지, scope isolation, 실제 final eval 필수, stop≠complete를 검사한다. 첨부 DREAM 56개 수용 명세를 보존하고 새 구현 테스트와 추적한다. 기반 ReplaySession unit tests만으로 전체 DREAM 연구 구현을 재현했다고 표시하지 않는다.

## Risks

기록의 coverage가 낮으면 replay 선별 효율이 작고 실제 탐색 비용이 커진다. 이 경우 데이터가 없는 이유와 실험 가치를 보고한다. 숨은 tool state·provider routing으로 input 동일성을 입증할 수 없으면 replay 판정을 보수적으로 제한한다.
