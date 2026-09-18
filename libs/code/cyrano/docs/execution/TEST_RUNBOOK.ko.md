# R3 실제 실행·인수 Runbook

## 1. 파일 적용

외부 네트워크가 가능한 개발 환경에서 공식 monorepo를 새 작업 디렉터리에 준비한다. 현재 사용자 작업트리를 reset하거나 덮어쓰지 않는다. 아래 SHA는 분석 snapshot이며 자동 최신 업데이트 대상이 아니다.

```bash
git clone https://github.com/langchain-ai/deepagents.git deepagents-cyrano
git -C deepagents-cyrano switch --detach 7f9e8ed3a555933902045792da9bb184950ee7b2
git -C deepagents-cyrano switch -c cyrano-assessment-r3
python apply_overlay.py --target /absolute/path/deepagents-cyrano
python apply_overlay.py --target /absolute/path/deepagents-cyrano --apply --receipt ../cyrano-overlay-receipt.json --link-agents
cd /absolute/path/deepagents-cyrano/libs/code
```

clone 명령은 새 checkout을 둘 위치에서 실행하고 installer 명령은 이 ZIP을 압축 해제한 kit 루트에서 실행한다. 상대 checkout 경로는 clone한 실제 위치로 고친다. dry-run이 conflict를 보이면 먼저 diff를 리뷰한다. `--force`, reset --hard, git clean을 우회 수단으로 쓰지 않는다.

## 2. 무과금 오프라인 자료·기반 확인

```bash
python cyrano/scripts/dev.py status
python cyrano/scripts/dev.py check
python cyrano/scripts/dev.py schemas
python cyrano/scripts/assessment.py validate
python cyrano/scripts/assessment.py inventory
python cyrano/scripts/assessment.py report
```

이 명령은 실제 모델·learning worker·원격 trace를 시작하지 않는다. validate는 source pack·15항목/40점·case ownership·계약/명세의 정합성만 확인한다. report는 미평가 scorecard를 표시하며 점수를 임의 생성하지 않는다. jsonschema·referencing·mistune가 없으면 해당 검사 blocked다. 설치가 필요하면 별도 개발환경에서 승인된 pinned dependencies를 준비한다.

## 3. native 환경·품질

```bash
uv sync --locked --group test
uv run --locked ruff --version
uv run --locked ty --version
uv run --locked python cyrano/scripts/dev.py quality
```

위 uv 명령은 **libs/code**에서 실행한다. 실제 lock이 해석되지 않으면 임의로 R2 lock을 덮지 않는다. quality runner는 설치 여부를 확인하고 missing/pin미확인 상태를 blocked로 보고할 수 있다. 개발 중 version probes 결과와 binary location을 runtime-lock에 넣은 후 source-native Ruff/ty·target adapter를 실행한다. strict 정규화 JSON parser를 지원하는지 각 버전의 --help/fixture로 확인한다.

## 4. 실제 제품 테스트 파일 구현·수집

`tests/cyrano_product/`의 구현 안내와 cases manifest의 `implementation_test_symbol`에 따라 product tests를 작성한다. 아래 product 명령은 구현 파일과 환경이 없으면 `BLOCKED_PRODUCT_TESTS_NOT_IMPLEMENTED`를 반환한다. 현재 ZIP에 가짜 skipped product test는 없다.

```bash
python cyrano/scripts/assessment.py product --collect-only
```

L3 native fake-model tests와 L4 live-model tests는 분리된 suite다. 실제 실행 adapter는 TS04–TS11에서 작성한다. 승인 budget·credential·sandbox 없이 live를 실행하지 않는다. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`만으로 candidate conftest를 안전하게 만드는 것은 아니다. trusted suite·observer·config는 sandbox 밖 evaluator가 제공한다.

## 5. 평가 실행 절차

평가 운영자가 source/policy/runtime/suite/rubric/task manifests를 봉인하고 typed EvaluationPermit을 발급한다. 정상 업무·범위 변경·오류·memory noise·실패 반복 과제를 미리 등록한다. 사례마다 before inventory→actual action→after inventory→expected assertions→receipt settlement→cleanup를 수행한다. paid call cap=0이면 실제 호출을 하지 않고 blocked다.

code 품질 원자 검토와 plan-review LLM 증거를 수집한다. memory 시험은 별도 두 프로세스와 새 thread로 수행한다. path B 개선은 같은 input conditions의 기준안·후보 실제 실행이며 단순 replay는 별도로 표시한다. 실패·cancel·skip·재시도를 지우지 않는다. independent reviewer와 trusted registry가 evidence subject를 확인한 뒤 점수 report를 발급한다.

## 6. Fail/blocked 처리

style/type 위반은 승인된 변경 scope에서 repair하되 scope 확대 시 plan-review를 다시 한다. 도구 설치·credential·sandbox 권한 문제는 환경 blocker이지 코드 품질 실패가 아니다. approved suite가 없어 0 tests면 제품 요구 미충족이다. unknown side effect는 상태를 unknown으로 유지하고 외부 결과 확인 전 자동 재시도하지 않는다. approval revocation·audit loss·secret suspicion은 dispatch를 중단한다.

최종 handoff에는 현재 15개 점수·근거·미검증 항목·hard gate 상태를 함께 내고 전체 release eligible 여부를 별도 표시한다. 이 ZIP을 압축한 시점의 foundation 결과와 나중의 실제 모델 평가를 같은 검사 시리즈로 합치지 않는다.
