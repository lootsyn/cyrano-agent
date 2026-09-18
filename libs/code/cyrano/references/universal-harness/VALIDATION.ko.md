# 검증 결과와 적용 범위

검사 기준일: 2026-09-15. 이 패키지는 설계·계약·참조 검증 산출물이다. 제품 구현의 운영 검증 보고서가 아니다.

## 실제 실행한 검사

| 검사 | 결과 |
|---|---|
| JSON Schema meta-schema 검사 | 15개 통과 |
| 정상 JSON 예시 | 14개 허용 |
| 오류 JSON 예시 | 14개 거부 |
| 첨부 원본 파일 | 14개 SHA-256 일치; 실제 업로드 ZIP bytes와도 비교 |
| 원본 수용 사례 보존 | 22개 Given/When/Then 원문 일치 |
| 참조 oracle 단위 테스트 | 35개 통과 |
| 테스트용 Ed25519 receipt | 정상 서명 검증, 본문 변조 거부 |
| SQLite DDL | 메모리 DB 생성, foreign key 거부와 FTS5 검색 smoke 통과 |
| Python 파일 syntax | AST parse 통과 |
| 40점 rubric | 20개 기준, 최대 점수 합40, test ID 참조 유효 |

## 수행하지 않은 검사

실제 dcode 설치/extension/middleware 동작, 모델 API 호출, prompt-cache hit·요금·지연, dcode 세션 간 기억 적용, 신뢰된 사용자 승인과 OS 격리 E2E, 124개 수용 사례의 제품 런타임 실행, baseline/holdout 개선 효과, dashboard/remote trace, 완성 구현에 대한 Black/Ruff/mypy 검사는 수행하지 않았다.

현재 검증 환경에는 dcode가 설치되어 있지 않다. reference tests는 dcode 대신 합성 사실로 kernel 의미를 검사한다. 124개는 실행 결과가 아니라 구현할 테스트 명세다. schema-only permit 예시는 서명된 실행 허가가 아니며, 테스트 receipt 공개키 역시 production 신뢰 목록에 넣으면 안 된다.

이 결과만으로 네 추가 요구사항에 40/40점을 부여하지 않는다. 실제 제품 점수는 운영 구현과 독립 검증 evidence가 준비된 후 `contracts/requirements40-rubric.json`으로 산정한다.

HTML 내부 anchor·중복 ID·패키지 SHA-256 manifest·ZIP CRC·상태 전이 참조는 별도로 확인했다. 실제 브라우저 시각 렌더링 검사는 Chromium 실행 파일이 없어 수행하지 못했다. HTML 파일의 구조와 내부 탐색 링크는 검사했다.

## 재현

`python tools/validate_package.py`를 패키지 루트에서 실행한다. 필요한 검증용 의존성은 별도 환경에 설치하고 고정한다. 실제 실행 로그는 `reference/TEST_OUTPUT.txt`, 기계 판독 보고서는 `VALIDATION_REPORT.json`이다.
