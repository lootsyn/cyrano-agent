# dcode 내부 Cyrano Monitor · 메뉴·화면·스트림 설계

문서 유형: 목표 상세 설계. 평가 4-1–4-4와 Memory 3-1–3-4의 운영 확인 화면이다. 외부 브라우저 dashboard를 기본으로 요구하지 않는다. dcode는 Textual TUI를 이미 사용한다. 이번 source의 `monitor/screen.py`는 주입 가능한 읽기 전용 화면 component이며, native 연결·실제 Textual 실행 증거는 RF07–RF09에서 필요하다.

## 1. 진입점과 native 변경

기존 `/trace`의 LangSmith 열기 기능은 유지한다. 새 `/cyrano`는 현재 요청의 Monitor 화면을 연다. 하위 문법은 `/cyrano monitor`, `/cyrano memory`, `/cyrano learning`, `/cyrano health` 네 가지 읽기 진입점이다. 새로운 top-level 별칭을 임의로 많이 늘리지 않는다. 모달 UI는 대화 내용을 모델에 보내거나 tool schema를 바꾸지 않는다.

`deepagents_code/command_registry.py`의 COMMANDS에 `SlashCommand(name='/cyrano', description='Open the local Cyrano monitor', bypass_tier=BypassTier.IMMEDIATE_UI, argument_hint='[monitor|memory|learning|health]')`를 등록한다. native command argument bypass map이 필요한지 `_can_bypass_queue`와 `IMMEDIATE_UI_ARG_FORMS`에서 확인한다. long-running agent 중에도 읽기 화면이 열려야 하지만 thread-switch 중에는 stale thread를 열지 않는다. 전체 handler는 `app.py` 실제 checkout에서 찾아 최소 분기로 연결한다. attach example은 patch 청사진이지 이미 적용한 코드가 아니다.

Python extension에는 register_command API가 없다. skill frontmatter나 extension Python만으로 native command를 만들었다고 하지 않는다. command metadata 변경 후 공식 `scripts/generate_commands_catalog.py` 또는 Makefile commands-catalog로 catalog를 재생성하고 native tests를 실행한다. native 파일은 이 ZIP에 덮어쓰기용으로 복제하지 않는다.

## 2. 화면 구성과 키

| 탭 | 표시 정보 | 선택 시 상세 |
|---|---|---|
| 요약 | request/plan/release, phase, outcome, elapsed, budget, coverage | plan revision·승인 상태·근거 |
| 흐름 | intake→interview→plan→review→approval→change→test→final→learning | 해당 event, parent/causes, redacted payload |
| 호출 | logical requests, physical attempts, retries, main/child/offload/classifier | 각 attempt·오류·usage missing |
| 변경·검증 | 승인 범위, changed files, 테스트 실행·판정, baseline failure | diff·argv·runner artifact |
| 기억 | queried/selected/injected/referenced/applied 단계, core/index freshness | 출처·조건·revision·tombstone/pending |
| 개선 | 후보→평가→리뷰→승격→새 task 적용, A/B·비교 지표 | delta diff, CI·holdout 상태, rollback impact |
| 도구·상태 | LSP/MCP/index generation, version/license, queue/DB/exporter | health/error·coverage gap·resource limits |

Tab/Shift+Tab은 focus, 방향키·PageUp/Down은 목록, Enter는 상세, Escape는 상세→Monitor→기존 chat 순으로 돌아간다. `r` 갱신은 search input focus 시 텍스트로 처리한다. Ctrl+C는 기존 native 인터럽트 의미를 유지하며 화면 닫기 때문에 agent를 취소하지 않는다. 현재 component는 Esc/r만 제공한다; 전체 focus·검색·탭 jump는 RF08 구현 대상이다. Ctrl+T·Ctrl+N 등 upstream 단축키를 임의로 빼앗지 않는다.

표시는 한국어/영어 사용자 설정을 따르되 machine status는 별도 저장한다. 색뿐 아니라 `통과/실패/차단/미실행/취소/불명/비활성` 문구를 항상 표시한다. connected 표시가 trace coverage=complete를 의미하지 않는다.

## 3. 120×40 기준 wireframe

```text
┌ Cyrano Agent · request R-42 · workspace W-A ────────────────────────┐
│ 연결: LIVE   단계: VERIFY   결과: 진행 중   원장: 582   계측: 7/8   │
│ 요약 | 흐름 | 호출 | 변경·검증 | 기억 | 개선 | 도구·상태              │
├────────────────────────────────────────────────────────────────────┤
│ 계획 rev 4 승인됨     source sha…     harness release sha…          │
│ 논리 요청 8  실제 시도 10  재시도 2  도구시작 19  도구거부 1        │
│ 입력 18,421  cache read 12,034(관측됨)  과금 불명 1건                │
│ 기억: 검색 3 → 주입 2 → 적용검증 1   후보 1 / 평가 대기             │
├────────────────────────┬───────────────────────────────────────────┤
│ 14:22 계획 리뷰 수정요청│ 첫 관측 실패: test.failed E-501            │
│ 14:23 계획 rev4 승인   │ 원인 확인: assertion mismatch              │
│ 14:24 코드 변경 2 files│ 근거: runner/test-report.json              │
│ 14:25 테스트 실패      │ 근본원인: 아직 불명 / retry 성공과 구분     │
│ 14:26 재작업 계획 중   │ Enter: 근거 상세                            │
├────────────────────────┴───────────────────────────────────────────┤
│ Esc 대화로 | Tab 이동 | / 검색 | r 갱신 | e 승인된 redacted export  │
└────────────────────────────────────────────────────────────────────┘
```

80×24에서는 위/아래 단일 컬럼과 가로 scroll 없는 compact table로 전환한다. 60×20 미만은 요약·필수 status·'창을 확대하세요'와 Escape만 보장한다. 긴 path/digest는 화면에서 생략하되 상세에는 full text copy가 가능하다. 한글·이모지의 terminal cell 폭은 Textual/Rich 측정을 사용하고 len(text)로 셀 너비를 계산하지 않는다. 스냅샷 테스트에 120×40, 80×24, 60×20, dark/light, 한국어를 포함한다.

## 4. Snapshot→stream 일관성

화면은 ControlQueryPort에서 `open_view(scope, request_id)`를 호출해 `{view_id,generation,snapshot_cursor,summary,rows,coverage,server_now}`를 받는다. subscription은 `after=snapshot_cursor`로 시작해 snapshot 사이 이벤트를 놓치지 않는다. global cursor의 숫자 건너뜀은 scope filtering일 수 있어 그 자체를 gap으로 판단하지 않는다. 서버가 retained range를 잃었거나 generation이 바뀌면 `reset_required`와 새 snapshot을 요청한다.

`MonitorDelta`에는 view_id/generation/commit_seq/event_id/event_type/payload가 있다. scope·generation 검사→중복 hash 검사→순수 reducer→bounded view 갱신 순서다. 같은 event ID·다른 payload는 충돌 경보. terminal event 누락은 unknown, start/finish 도착 순서 역전은 pending으로 결속한다. producer_seq와 중앙 commit_seq를 혼동하지 않는다. canonical payload를 UI가 수정해 완성 상태를 만들 수 없다.

화면의 row cap 초과 때 history를 버린 뒤 총계를 다시 계산하면 안 된다. authoritative summary checkpoint와 page cursor를 유지한다. 현재 순수 projection은 cap 초과 시 `SNAPSHOT_REQUIRED`를 반환한다. 지속 서비스에는 RF08에서 snapshot summary+delta 구조를 연결한다.

## 5. 비동기·busy·연결 끊김

별도의 Textual worker가 poll/stream을 읽는다. blocking DB/network를 UI event loop에서 수행하지 않는다. 중복 refresh는 같은 worker group에서 cancel/replace, 화면 unmount나 thread switch는 해당 view subscription만 취소한다. 원래 대화 실행·승인 대기 worker를 중지하지 않는다.

초기 refresh 목표는 250ms coalesce, 서비스 poll 기본1초, page200·max1000·body16KiB·queue2000는 정책 초깃값이다. 실제 부하 검증 전 최적값이라 하지 않는다. queue overflow는 transient rows coalesce와 resnapshot으로 복구하고 audit event는 서버에 남는다. reconnect는 bounded backoff와 cursor 복구. 연결이 끊기면 마지막 업데이트 시각, stale, partial을 계속 표시하고 count를 0으로 덮지 않는다.

## 6. 권한·표시·사용자 제어

기본 화면은 read-only다. source path·tool result·log에 Rich markup/ANSI OSC/터미널 title/클립보드 control을 해석하지 않는다. 렌더는 literal Text 또는 markup=False, Cc/Cf/SURROGATE 필터, 크기 제한을 사용한다. transport 전에 redaction하고 export도 같은 승인된 view에서 생성한다. 화면 sanitization은 secret redaction을 대신하지 않는다.

승인·반려·메모리 삭제·학습 중지·rollback은 별도 상세 확인 화면으로 분리한다. trusted UI가 actor/session/nonce/expected revision/digest를 담아 ApprovalBroker endpoint를 호출한다. endpoint는 signed permit과 동일 권한 경계를 가진다. 모델이 command 텍스트를 출력하거나 tool이 UI를 클릭한 self-report로 사람 승인을 생성할 수 없다. native console과 operator control plane이 분리된 경우 trusted channel이 없으면 조회만 가능하며 approve 버튼 비활성 사유를 표시한다.

pending 개선 화면에는 전체 diff·근거·평가 범위·불확실·영향 run을 확인하게 한다. 단순 gist만 보고 high-risk skill code를 승인하지 않는다. critical incident는 pause/revoke를 별도 인증 후 실행하며 모니터 창을 닫아도 incident가 해결됐다고 표시하지 않는다.

## 7. headless·ACP와 테스트 경로

ACP stdio에는 ANSI/TUI를 출력하지 않는다. headless/ACP도 동일 event producer와 QueryPort를 사용하고 결과 JSON 또는 별도 `python -m deepagents_code.cyrano.monitor` reader로 조회할 수 있도록 구현한다. 이 명령은 native 서비스 연결 후의 목표이며 현재 제공 demo는 `python cyrano/scripts/monitor_demo.py`다. demo는 합성 입력을 명시하며 서버에 연결하지 않는다.

수용: 모델 호출 중 Monitor 즉시 열림, 거부 workspace/원시 secret 미노출, shell/child/내부 grader 비용 구분, 취소와 unknown 보존, snapshot/reconnect/no gap, 한국어 resize, markups literal, Escape 후 chat focus, native `/trace` 회귀 없음. 추가 TUI 테스트 코드는 `tests/cyrano_product/test_r5_rf08.py`에 RF08이 구현한다. 순수 reducer test와 native Textual end-to-end를 같은 결과로 합치지 않는다.

## 10. 권한 철회와 화면 잔존 데이터

조회 실패가 단순 network 문제인지 권한 철회인지 확정할 수 없으면 현재 component는 모든 pane의 이전 내용을 숨긴다. 이전 민감내용을 stale이라는 꼬리표만 붙여 계속 보여 주지 않는다. 구분 가능한 authenticated transport를 구현한 뒤에도 권한 철회·scope변경은 즉시 clear하며, 제한된 offline view 보관은 별도 권한·보존 정책이 있어야 한다. malformed view/유효하지 않은 값/원시 exception은 화면에 출력하지 않는다. 화면 teardown과 late callback 경합에서 이미 unmount한 widget을 갱신하지 않는다.

## 계획 공동 검토·결정 화면

기존 `/cyrano` native 화면에 `계획/결정` 진입을 추가한다. 구체 권한·판정은 [계획 상세 설계](features/2026-09-16-plan-memory-execution.ko.md)가 소유한다. 일반 plugin에 존재하지 않는 slash command 등록 API를 가정하지 않고 WP06·WP13이 native command registry, 현재 handler, 인증된 control client를 연결한다.

화면은 `목표·범위 / 변경 파일·데이터 / 대안·위험 / 작업·의존 / 테스트·완료 조건 / 비용·권한 / 미해결 finding / revision diff`를 동일 packet에서 읽는다. 선택은 `질문`, `수정 요청`, `보류`, `거부`, `계획 동의`, `실행 허가`로 구분한다. 실행 허가는 필요한 계획 review가 유효한 경우에만 별도 목적의 요청으로 보여준다. 최종 인수·source apply·publish도 별도 목적이다.

기본 선택 없음, stale packet에서 승인 비활성, 중복 클릭 idempotency, 만료 시 재표시, Escape/창닫기 defer, thread 전환 시 민감 데이터 제거를 구현한다. 한글 폭·긴 경로·ANSI·paste 제어문자·키 반복·초기 focus·좁은 터미널을 시험한다. 사람이 실제 텍스트를 읽었는지 UI가 보증한다고 주장하지 않는다. 화면 조회·diff 열람은 LLM 호출 없이 처리하고, 사람에게 필요한 설명 생성만 명시적인 model task와 비용으로 기록한다.

사용자가 수정한 문장은 plan patch proposal이다. 검토 없이 scope·test·budget을 변경해 이미 발급된 permit으로 실행하지 않는다. `submit_response`는 expected request_revision/display_digest를 포함하며 원장 재검증이 실패하면 UI가 로컬에서 성공으로 보정하지 않는다.
