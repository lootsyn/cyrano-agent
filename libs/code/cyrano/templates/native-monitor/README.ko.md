# Native 연결 patch 청사진 — 아직 적용되지 않음

RF07은 실제 pinned checkout에서 command_registry.py, app.py, command별 busy bypass map, native test·catalog generator를 먼저 읽는다. `app.py` 원문은 이번 원격 조회에서 size limit으로 읽지 못했으므로 이전 분석팩의 `_handle_command` 위치를 현재 정확한 line으로 가정하지 않는다.

1. COMMANDS에 `/cyrano` 한 항목과 네 가지 읽기 하위 command를 등록한다. 클래스·enum은 source 문서에서 확인한 SlashCommand/BypassTier를 사용한다.
2. native handler의 dispatch에서 현재 trusted request ID·workspace ID를 가져와 MonitorQueryClient를 생성하고 CyranoMonitorScreen을 push한다. 이 호출은 agent에게 user message를 enqueue하지 않는다.
3. memory/learning/health 하위 인자는 target tab만 바꾼다. 알 수 없는 인자는 usage를 보여 주고 모델로 넘기지 않는다.
4. query transport는 기존 server 인증 연결을 우선 재사용한다. 새로운 localhost 포트가 필요하면 별도 인증·origin/CSRF·lifetime 정책을 먼저 구현한다. DB direct read를 UI에 넣지 않는다.
5. `/trace`, `/cost`, `/context`의 기존 동작을 보존하고 native 명령 catalog·tests를 갱신한다. app source를 복제해 wholesale replacement하지 않는다.
6. actor별 test는 RF07/RF09 수용 사례를 따른다. stub query 화면을 실제 runtime 계측 완료로 보고하지 않는다.
