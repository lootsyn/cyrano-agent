# 패키지 검증 범위

실제로 확인한 항목:

- 모든 JSON 파일이 파싱된다.
- 두 JSON Schema가 Draft 2020-12 메타스키마 검사에 통과한다.
- 예시 worker 결과가 worker schema에 맞는다.
- 추가 `approved` 필드, 음수 revision, counterexample 본문 누락을 worker schema가 거부한다.
- 패키지 파일이 존재하며 비어 있지 않다.

확인하지 않은 항목:

- Gajae/Ouroboros 테스트 실행 또는 실제 인터뷰 비교.
- 이 설계 커널의 구현·상태 전이·권한·암호학적 검증.
- fixtures/readiness-cases.json의 22개 정책 사례 실행.
- 실제 호스트 연결, MCP 실행, 독립 에이전트 호출, 성능·비용 개선.

따라서 이것은 **설계 파일의 구문 검증**이지 완성 플러그인의 테스트 통과 보고서가 아니다.
