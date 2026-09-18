# Memory·자기개선·모니터링 개발 실행 절차

문서 유형: 실행계획. 제품 테스트 파일·fixture·service는 담당 RC에서 구현한다. 아래 명령은 구현 후 수행할 native test 절차이며 이번 ZIP에서 이미 실행된 제품 검사가 아니다. 기준 cwd는 `<deepagents>/libs/code`.

## 1. 공통 실행 전 조건

RC00 native environment, approved isolated workspace, 외부 control home, 서로 다른 actor/evaluator principals, pinned source/runtime/policy/suite, 계획·비용·테스트 scope 승인을 확인한다. 비밀은 OS secret store 또는 승인된 env source에서 주입하고 raw event 파일에 넣지 않는다. 테스트 임시 DB·sandbox는 사용자 실제 프로젝트 데이터와 분리한다.

각 사례의 fixture builder는 `workspace`, `control_home`, `tenant_a`, `tenant_b`, `baseline_release`, `task_spec`, `fault_injector`, `evidence_dir`, `cleanup_handle`을 반환한다. builder는 current suite에서 고정하며 model/candidate가 수정할 수 없다. 실제 wall-clock wait 대신 controlled clock을 쓰는 component test와 real process/native runtime test를 구분한다.

## 2. 공통 evidence 폴더

`cyrano/evidence/runs/<opaque-run-id>/`는 개발 시만 사용한다. 운영 storage는 checkout 밖이다. 각 실행에 `run-binding.json`, `plan.json`, `plan-review.json`, `approval-ref.json`, `input-manifest.json`, `events.jsonl`, `artifacts/`, `case-results.json`, `metrics.json`, `coverage.json`, `cleanup.json`, `independent-review.json`을 남긴다. 없음은 null+사유이지 빈 통과 artifact가 아니다.

EvidenceWriter는 raw artifact를 닫고 SHA256을 계산한 뒤 evaluator-owned manifest에 등록한다. source/runtime/suite/policy가 다른 결과를 하나의 점수로 합치지 않는다. 새 source 수정 후 묵은 test result를 완료 근거로 사용하지 않는다. 단위 fixture의 합성 승인 값은 trusted product approval로 취급하지 않는다.

## 3. 3-1 지속성 실행

process A를 `subprocess.Popen`으로 시작해 scoped project rule과 episode를 저장·승격한다. 저장 전후 DB/event cursor를 기록하고 정상 종료한다. 테스트 메모리/공유 Python object를 B에 넘기지 않는다. B는 새 process/new thread/no transcript로 시작하고 persistent store 위치와 principal만 받는다. query 결과 digest와 native context projection을 확인한다. 이어서 다른 workspace, TTL 만료, dependency 변경, 삭제 tombstone 사례를 실행한다.

실패하면 DB 파일·principal·release·query error를 분리해 조사한다. stale FTS가 query result 0 또는 다른 tenant 본문을 만들면 contract failure. process A와 B가 같은 in-memory dict를 공유한 테스트는 3-1 제품 증거에서 제외한다.

## 4. 3-2 실제 활용 실행

준비된 작업에 필요한 규칙(예: 특정 검증 recipe)을 active memory로 준비한다. user prompt에는 해당 규칙 정답을 직접 넣지 않는다. 새 작업을 접수하고 queried→selected→request/context→plan/code/test chain을 기록한다. model이 memory ID만 출력한 control 사례와 plan에 recipe를 포함해 실제 실행한 사례를 구분한다. application checker의 false-positive를 ID-only 반례로 검사한다.

평가자는 plan와 code/result artifact를 별도 읽고 memory revision과 영향을 확인한다. 온/오프 비교는 별도 effectiveness 실험이며, 기억을 많이 읽었다는 이유로 task effect를 가산하지 않는다.

## 5. 3-3 후보 생성 실행

정상 보안 거부/TDD red/취소와 진짜 재발 오류를 가진 episode 묶음을 고정한다. learning worker를 제한 예산·max jobs로 실행한다. system procedural block, skill, task memory 후보가 각각 evidence·hypothesis·alternative·counterexample·patch·eval plan을 갖는지 검사한다. 보호 root/평가 기준 수정 후보는 거부돼야 한다. 모든 active release·현재 실행 프로세스 파일의 preimage/postimage는 같아야 한다.

## 6. 3-4 개선·회귀·다음 작업 실행

사전 고정 family split에서 actual paired evaluation을 수행한다. 실행 순서·budget·provider/seed/환경·source·memory release를 기록한다. 한 후보는 유효 개선, 한 후보는 안전 회귀, 한 후보는 불확실 효과를 만들도록 fixture를 설계한다. effect를 사전 정답으로 가짜 reporting하지 말고 실제 runner가 그 행동 차이를 측정하게 한다. 통과 후보만 review→approval→release CAS 경로로 승격한다.

새 process/new session을 실행해 새로운 artifact digest가 실제 context/skill에 반영되는지 확인한다. 기존 run은 기존 release 유지, revoke는 다음 dispatch에서 차단/재결속한다. rollback 때 사용자 코드 파일은 자동 원복되지 않는다는 사실을 UI/API evidence에 표시한다.

## 7. 4번 전체 흐름·오류·수치·조회 실행

A 요청은 계획 수정→승인→코드 변경→test 실패→재작업→최종 결과로 실행한다. B 요청은 model timeout 2 retry, child 호출, denied tool을 포함한다. C는 exporter down, D는 local audit storage fault, E는 worker crash를 주입한다. first-failed-stage는 trusted runner/test event 기준으로 계산한다.

기대 수치 사례: main logical L1의 physical A1/A2/A3와 child logical L2/A1이면 logical=2, physical=4, retries=2. 중복 event 재전송·순서 역전·resume 후에도 동일해야 한다. unknown usage는 null, duration clock mismatch는 invalid/unknown. 승인 거부 tool은 requested/denied에만 포함한다.

새 read-only 사용자 세션에서 request list→timeline→trace tree→실패 artifact→관련 plan/review/memory/learning을 탐색한다. cross-scope ID·민감 artifact·무단 export가 차단되는지 검사한다. API test와 실제 UI smoke를 별도로 기록한다. CLI/HTTP endpoint가 구현되지 않았으면 해당 화면/명령을 사용 가능한 것처럼 문서화하지 않는다.

## 8. 구현 후 명령

각 RC 상세 문서에 정확한 파일과 test symbol이 있다. 예를 들어 Memory persistence와 monitoring metrics는 다음과 같다.

```sh
uv run --no-sync pytest tests/cyrano_product/test_r4_rc30.py --collect-only -q
uv run --no-sync pytest tests/cyrano_product/test_r4_rc30.py -q
uv run --no-sync pytest tests/cyrano_product/test_r4_rc41.py -q
uv run --no-sync pytest tests/cyrano_product/test_r4_rc43.py -q
```

현재 파일이 없으면 먼저 RC 설계를 구현한다. 없는 파일을 `pytest.skip`만 넣어 통과시키지 않는다. runtime/provider 비용 허가가 없는 product case는 명시 not_run/blocked. 결정적 fake 모델은 observer/reducer 단위 시험에만 쓰며 실측 provider·성능 개선의 증거가 아니다.

## 9. 중지·복구·결과

critical audit unavailable, scope/approval bypass, secret leak, oracle tamper가 발생하면 run을 중지하고 incident evidence를 고정한다. external unknown outcome은 remote receipt로 reconcile한다. evidence 보존 이후 소유 temp root만 삭제한다. 테스트 프로세스·lease·network proxy가 남지 않았는지 확인한다.

case result enum은 passed/failed/blocked/cancelled/unknown/not_run. 제품 항목은 mandatory 모든 증거가 있어야 충족하며 inconclusive 개선은 배포하지 않는다. 공식 채점과 개발용 diagnostic 점수를 분리하고 40점 evidence evaluator가 source/suite binding을 다시 검증한다.
