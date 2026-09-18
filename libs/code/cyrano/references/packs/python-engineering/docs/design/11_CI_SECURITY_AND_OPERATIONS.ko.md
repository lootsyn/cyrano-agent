# 11. CI, 보안, 운영

## 11.1 CI의 역할

로컬 agent가 규칙을 건너뛰어도 merge 직전에 같은 정책과 요구 체크를 독립 실행한다.
CI는 Skill이 실행됐다는 텍스트가 아니라 실제 candidate commit/snapshot을 검사한다.
`quality`라는 job 이름이 있다는 것과 branch 보호에 required check로 등록됐다는 것은 다르다.

도입 시 maintainer가 required status check와 보호된 workflow/policy 경로 검토 규칙을 설정한다.
권한이 없으면 그 설정을 “완료”로 보고하지 않고 배포 blocker로 기록한다.
CODEOWNERS 파일만 추가했다고 branch 보호가 자동으로 활성화된다고 설명하지 않는다.

## 11.2 CI topology

```text
approved policy/runner release ───────────────┐
                                           ↓
PR candidate → unprivileged sandbox → tool receipts → trusted aggregation
                                           ↓
                           required checks + immutable candidate binding
                                           ↓
                        quality/final = success 또는 failure
```

첫 구현은 ubuntu runner에서 실행한다. checkout과 bootstrap은 최소 read 권한으로 수행하고
candidate test 프로세스에는 repository write token, release token, cloud credential을 전달하지 않는다.
외부 PR 코드/설치 script를 높은 권한의 `pull_request_target` context에서 실행하지 않는다.
전체 SHA로 고정한 검토된 actions/runner release를 사용하고 tag만을 불변 pin으로 간주하지 않는다. [S15]

승인된 runner artifact는 **candidate branch에서 import하지 않는다**. candidate가
`scripts/quality_gate.py`를 `return 0`으로 바꿔도 CI의 최종 판정을 바꾸지 못하게 한다.
정책/runner 자체 변경 PR은 이전 trusted runner와 보호된 acceptance test로 검사하고,
새 release가 승인되기 전에는 새 정책을 검사 기준으로 승격하지 않는다.

## 11.3 job 단계의 정확한 동작

1. 입력 검증: event의 실제 candidate SHA, base SHA, repository identity를 고정한다.
2. 정책 확보: 승인된 immutable release에서 policy/runner/toolchain lock을 읽는다.
3. candidate 준비: source snapshot에 build/test resources 포함, Git credential은 제거한다.
4. 환경 준비: 승인된 uv version/Python image로 `uv sync --locked`에 상응하는 install을 sandbox에서 수행.
5. quality guard: config와 tests가 기준을 약화하는지 확인한다.
6. static checks와 필수 tests를 실행하고 structured 결과를 수집한다.
7. assertion/acceptance 의미의 review 조건을 확인한다.
8. artifact export: raw restricted logs와 redacted report를 구분해 보존한다.
9. final aggregate: 필수 job 누락/skipped/cancelled/errored는 success가 아니다.
10. candidate SHA와 merge 대상 SHA가 달라지면 다시 검증한다. merge queue 사용 시 합성 merge도 검사한다.

출력 job이 `if: always()`로 실행돼야 실패 증거를 수집할 수 있지만, `always()`라는 이유로
성공 처리하지 않는다. `continue-on-error`로 필수 실패를 감추지 않는다.
path filter가 Python gate를 건너뛰는 경우도 required status 의미를 명확히 한다.
문서-only 변경의 not applicable은 diff inventory가 확인해야 하며, pyproject/conftest/CI 변경을
문서 작업으로 분류하지 않는다.

## 11.4 저장소마다 달라야 하는 것

Python 버전·workspace source roots·test entry point·외부 서비스 의존성은 inspect 결과를 사용한다.
UDH 예제의 `packages/*/*`를 일반 단일 패키지 repo에 그대로 넣지 않는다.
이미 mypy를 쓰는 프로젝트에 Pyright를 자동 설치하지 않는다.
기존 failing tests가 있으면 root 원인을 해결하거나 정확한 도입 blocker를 기록한다.

## 11.5 운영 실패와 rollback

도구 upgrade는 독립 작업이다. 이전 pin과 새 pin을 같은 fixture/test corpus에 실행해
rule 변화와 baseline invalidation을 확인한다. 설치 실패는 ERROR_ENV_SETUP이지 lint FAIL이 아니다.

새 Skill/정책 release 회귀 시 승인된 이전 bundle로 되돌린다. 진행 중 attempt는 자신이 시작한
release를 계속 참조하거나 명시적으로 취소·재시작한다. 중간에 toolchain/Skill을 갈아끼우지 않는다.
rollback은 모델이 임의로 실패 테스트를 제거하는 작업이 아니다.

컨테이너 image tag, system Python minor만으로 reproducibility를 보장하지 않는다.
정확한 patch/distribution/lock/image digests를 보고서에 남기고 플랫폼별 차이를 인정한다.
로컬 우연한 PASS와 CI FAIL이면 둘의 snapshot/config/environment 차이를 먼저 조사한다.
