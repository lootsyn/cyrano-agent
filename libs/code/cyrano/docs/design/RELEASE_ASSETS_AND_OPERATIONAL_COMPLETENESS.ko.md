# 제품 완성도·배포·안전한 운영에 필요한 보완

문서 유형: 목표 상세 설계. 기존 설계의 대체가 아닌 RF10–RF11의 구현 기준이다.

## 1. 기능 가용성 상태를 하나로 합치지 않는다

각 기능은 configured→installed→probe_passed→authorized→enabled를 별도로 기록한다. runtime이 없으면 `planned`, 설치 실패면 `failed`, 아직 검증 전이면 `not_tested`다. skill에 도구 이름이 있어도 registry에 없으면 그 skill을 usable로 표시하지 않는다. 개발용 provider를 제품 settings에 자동 복사하지 않는다.

`CapabilityReport`는 source/runtime/tool/asset/permission/coverage digest와 테스트 ID를 가진다. governed launch는 필수 contract에 한해 verified를 요구하고 optional provider 부재는 feature-specific disabled로 둔다. licensing flag 미승인 Serena는 제품 manifest에 들어갈 수 없다. operator가 raw MCP full tools를 붙여 넣었을 때 risk scan이 경고하고 governed tool gateway를 거치기 전 미활성으로 표시한다.

## 2. Skill·prompt·schema asset의 실제 패키징

canonical authoring files는 development resources에 있고 wheel의 runtime asset은 generator가 만든 immutable projection이다. `AssetManifest`는 logical_id, type, canonical_path, content_sha256, dependency_refs, license, evaluation_refs, release_digest를 기록한다. Python code의 import 경로와 asset의 pathlib 접근은 importlib.resources를 사용한다. source checkout 상대 경로가 wheel/zip import에서 작동한다고 가정하지 않는다.

RF10은 현재 dcode hatch의 include 규칙을 확인하고 필요한 `.json`·`.yaml`·`.md`·`.tcss` 파일을 명시적으로 추가한다. clean wheel 설치 환경에서 자산 존재·hash·skill discovery·tool binding·native dcode invocation을 검사한다. 반대로 development corpus/예전 ZIP/증거/secret/example endpoint가 wheel에 섞이지 않아야 한다. native dependency upgrades는 별도 lock/version 리뷰이고 resolver 충돌을 무시하는 override로 해결하지 않는다.

## 3. Migration·backup·삭제와 rollback

DB migration은 인접 버전·checksum·단일 writer·backup receipt·crash recovery를 가진다. 코드 release rollback이 DB downgrade를 자동 수행하지 않는다. 복구 지원 경로가 없으면 운영자는 이전 release로 pointer만 바꾸지 않고 compatible restore 또는 forward fix를 선택한다. backup 복구 후 tombstone·revocation ledger를 먼저 재생해 삭제한 기억과 revoked skill이 부활하지 않게 한다.

모델 cache나 외부 trace의 삭제는 provider 제약을 공개하고 별도 작업 상태로 남긴다. 예산·승인·holdout은 학습 후보가 변경할 수 없다. 취약 package 발견 시 영향 source/install/release를 역추적하고 해당 provider 비활성→자식 process 종료→새 lock 검토→회귀→새 epoch 순서로 복구한다.

## 4. 실험의 비용·성능·가용성

Foreground, background refinement, indexing, tool bootstrap, evaluation의 비용과 CPU/RAM/wall time을 구분한다. 한 번의 성공한 개선으로 비용 절감 확정하지 않는다. memory/skill 개선의 cumulative cost와 재발 감소를 함께 보고한다. 매 turn full transcript fork보다 terminal/교정/예산 trigger가 기본이며, 모델별 최적 prompt 분기는 만들지 않는다.

기본값은 bounded enabled components만 실행한다. network unavailable, disk full, malformed index, obsolete policy, missing optional dependency는 구별된 오류다. 정상 권한 거부를 개선 대상으로 삼아 승인 제거하는 후보를 만들지 않는다. deterministic retry 가능한 실패와 unknown external outcome을 분리한다.

## 5. 최종 40점·납품 gate

1번은 scoped Ruff+native ty 외 docstring 역할·입출력·예외의 의미 검토를 요구한다. 포매터만 통과하고 10점이라고 하지 않는다. 2번은 모든 native mutation 경로의 실제 차단과 범위 변경 재승인을 요구한다. 3번은 새 프로세스의 memory 적용과 개선 후 새로운 작업의 행동을 요구한다. 4번은 사용자 TUI에서 요청을 찾아 최초 실패 근거까지 가는 경로와 계측 누락 표기를 요구한다.

artifact/schema test 결과는 preparation evidence이고 runtime/효과 점수와 별도다. CLI screen demo의 합성 PASS를 운영 Monitor PASS로 사용하지 않는다. 도구를 많이 설치했다거나 논문을 많이 인용한 것으로 가점을 주지 않는다. 외부 패키지 제거 상태의 기본 기능 회귀도 최종 수용에 포함한다.

## 1. 이번에는 migration을 실행하지 않는다

현재 작업은 문서만 추가한다. dcode 최신 main의 0.1.70 release commit을 확인했지만 기존 0.1.69 기준을 바꾸지 않는다. [NS01](../reference/SOURCES.ko.md#ns01) WP00에서 실제 checkout과 upstream 차이를 비교하고 검토된 변경만 채택한다. 새 provider/package 설치·global config 변경·DB 변환·plugin 활성화는 없다.

## 2. 향후 단계

`off → observe_only → isolated_shadow → gated_canary → enabled` 상태를 feature별로 둔다. 한번에 전체 하네스를 바꾸는 big-bang rewrite를 하지 않는다. observe_only는 의도·결과를 기록할 뿐 권한을 완화하지 않는다. isolated_shadow는 실제 원본 쓰기·push·결제·네트워크 부작용을 두 번 일으키지 않는 모사·사본 실행만 허용한다.

feature 조합은 검토된 matrix에 한정한다. 신규 memory selection과 신규 provider transform을 동시에 바꾸면 효과 귀속이 불분명하므로 먼저 개별 비교 후 interaction 회귀를 수행한다. 값이 지정되지 않은 feature를 자동 활성화하지 않는다.

## 3. durable 형식의 변경

기존 schema version의 필드 의미를 바꾸지 않는다. reader/writer compatibility 표, adjacent migration, 최소 rollback 기준, backup·검증·복구 명령이 있어야 한다. 원본을 보존한 사본에서 migration dry-run을 수행하고 changed-record count·orphan refs·deleted-memory resurrection을 검사한다.

코드 rollback과 DB rollback은 다르다. 새 schema를 쓴 뒤 과거 바이너리를 자동으로 시작하면 corruption이 생길 수 있으므로 supported reader 확인 후 전환한다. irreversible migration은 별도 허가와 복구 가능한 export를 요구한다.

## 4. 공급망과 설치

외부 tool을 제품에 배포할지 개발에만 쓸지 각각 기록한다. lock은 실제 resolver로 생성한 결과여야 하며 이 문서의 예시 버전을 lock이라고 부르지 않는다. binary hash, license/notice, optional native build, platform support, egress/model download, SBOM·취약점 정책을 확인한다.

skill은 텍스트라도 코드·script resource가 있으면 실행 패키지다. 설치 hook·npm lifecycle·Python build backend·LSP plugin config도 임의 코드를 실행할 수 있다. 범용 scanner를 read-only file tool로 포장했다고 안전하다고 판단하지 않는다. agent가 설치 승인·신뢰 root·hidden test를 고칠 수 없어야 한다.

## 5. API와 명령의 변동

공식 branch/main·latest 문서는 변할 수 있다. 개발 시작 시 URL, ref, content hash, 관측 날짜, scope, 실제 실행 상태를 runtime compatibility report에 묶는다. closed source는 API conformance로만 검증하고 내부 동작을 가정하지 않는다. schema change가 있으면 tool exposure와 cache epoch·permission receipt도 갱신한다.

## 6. 되돌리기

자동 rollback은 알려진 안전 release로 신규 dispatch를 바꾸는 것부터 시작한다. 진행 중 위험 작업을 취소하고 unknown effects를 조사한다. 사용자 source 파일을 무조건 checkout/reset/clean하지 않는다. 복원은 receipt가 소유한 artifact·record에 한정하며 이후 사용자 변경과 충돌하면 중단한다.

최종 출시 조건은 기존 40점 평가의 15항목에 실제 증거를 연결하는 것이다. 이 문서와 pure fixture가 완성됐다는 이유로 점수를 올리지 않는다. cache나 throughput이 좋아져도 승인 우회·의도 위반·secret 유출·거짓 완료를 상쇄할 수 없다.

## 완성도 점검에서 빠지기 쉬운 경계

선택 도구의 설치 성공과 model-facing tool 활성화를 분리한다. source pin·transitive lock·build script·라이선스·network·모델 파일을 검토하고 실제 결과를 해당 sandbox에서 probe한 뒤 allowlist를 만든다. 개발용 Serena/Graphify/QMD 인덱스·HOME·자격증명을 제품에 그대로 복사하지 않는다. 상태 디렉터리와 provider 모델 파일은 현재 ZIP 납품 범위에서 제외한다.

대상 repository에 `.git` symlink, submodule, Windows 대소문자 충돌, reserved name, CRLF, executable mode, untracked secret이 있으면 일반 파일 복사로 처리하지 않는다. 검증한 manifest와 승인된 snapshot recipe를 사용한다. 임시 worktree는 사용자 변경과 유일한 복구본을 보존하며 wholesale clean을 실행하지 않는다.

Docker socket이나 host directory 전체 writable mount는 서로 다른 process라는 이유만으로 trust boundary가 되지 않는다. 개발 advisory와 governed 운영을 구분한다. 정책을 설치했다고 raw execute 경로의 우회 차단이 증명되지 않으므로 모든 도구 경로와 headless/ACP/child/재개에 대한 무효과 반례를 실제로 실행한다.

출시 후보의 검증은 산출된 wheel과 clean environment에서 수행한다. editable source test만으로 package data·skill resource·native CLI entrypoint가 배포된다고 단정하지 않는다. 복구는 harness release, 제품 DB, 고객 코드, 외부 효과를 각각 판정하며 하나의 'rollback success'로 합치지 않는다.
