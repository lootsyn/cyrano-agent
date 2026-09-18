# 평가 기준 기반 R4 보완 점검

문서 유형: 개발 점검 기록. 다음 판정은 이전 파일과 현재 소스를 읽은 정적 분석이며 실제 제품 성능/보안 감사 결과가 아니다.

| 구분 | 발견한 공백 | 이번 반영 | 남은 실제 검증 |
|---|---|---|---|
| A/E | overlay의 source 경로와 base 실행 코드의 구분 부족 | code-root 복사 폴더, 소유권 표, prepare/verify 가이드 | actual clone/native import/build RC00 |
| F | 미합의 이전 이름이 코드·문서·schema에 확산 | Cyrano active rename, history 원문 보존, 승인/DB 자동 변환 금지 | 운영 데이터 존재 시 별도 migration |
| 1-1 | 이전 style finding과 unavailable Ruff/ty | 고정 native toolchain·scope·CI 명령과 RC01 책임 | 모든 finding 수정·실제 tools 실행 |
| 1-2 | import/name style와 namespace rename 추적 부족 | 모든 active import/schema/path 교정; source manifest·회귀 | native lint+ty와 public naming review |
| 1-3 | docstring 존재만 검사하면 의미 오류 놓침 | 반환·예외·side effects와 실제 코드 비교하는 독립 review 사례 | product 함수별 reviewed doc evidence |
| 2-1/2-2 | 계획 문서와 실제 변경 permit의 결속 부족 | typed plan template·scope/source/test binding 명시 | actual broker prewrite guard |
| 2-3/2-4 | reviewer 독립성/범위 변경 재승인 증거가 약함 | review finding disposition과 stale approval 반례 | file/shell/MCP/child/headless/ACP/resume 우회 테스트 |
| 3-1 | memory selection만 있고 장기 저장 API 빈약 | immutable revision/release, transaction/outbox, process A/B | WP11/RC30 native 지속성 |
| 3-2 | reference와 실제 적용의 구분 구현이 없음 | view/request/application checker·삭제·stale 상세 | RC31/32 실제 행동 증거 |
| 3-3 | generic query/reflect 함수만으로 구현 가능성 낮음 | 표면별 patch/impact/학습계획·권한·worker lease | RC33 실제 후보 생성 |
| 3-4 | next task 실제 loading chain과 불확실 효과 처리 부족 | actual paired·CI·regression·release→next-run chain | RC34–36 실제 평가/배포 |
| 4-1/4-2 | event catalog 존재만으로 전수 수집 보장 불가 | trusted producer·epoch/dedupe·transaction·failure source | RC40/41 actual native coverage |
| 4-3 | logical/physical retry, null cost, 시간 기준이 모호 | 계수·latency·coverage 정의, 중복/역전 반례 | reducer/native 측정·부하 |
| 4-4 | coverage 객체만 있고 Trace 조회 경로 없음 | query API·read-only UI·ACL·redaction·복구 | RC42/43 실제 조회·원인 탐색 |
| C | 참고/설계/작업/실행이 긴 notes와 generated에 혼재 | 유형별 이동·catalog·INDEX·작은 readset router | 실제 개발 agent loader 인식·cache usage |
| 전체 | JSON/prompt resources가 native wheel에 안 들어갈 수 있음 | resource compiler/native packaging 소유 지정 | fresh install·기존 checkout 없는 smoke |
| 전체 | renamed schema가 이전 승인을 유효화할 위험 | 원형 R3 schema 보존·new namespace authority 독립 | 재발급·migration 검증 |

현재 정적 준비 수정은 completed_preparation, 제품 기능은 planned로 구분한다. 문서가 상세해졌다고 3·4번 20점 또는 총40점을 부여하지 않는다. official score는 미평가 null을 유지한다.

재압축 보완: 이전 재압축 스크립트가 개발 자료 root만 선택해 제품 소스가 빠질 수 있었다. 이제 소유한 code-root 추가분 전체를 수집하고, native base/승인 후 native 수정은 포함하지 않는다고 결과에 명시한다. 실제 fork release는 WP19/22에서 전체 commit과 native diff를 검증해 패키징한다.
