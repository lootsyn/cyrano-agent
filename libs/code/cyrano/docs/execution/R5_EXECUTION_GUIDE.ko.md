# Cyrano Agent · 개발 수행 가이드

문서 유형: 실행 가이드 — 현재 단일 기준.

## 1. Base와 작업 위치

Base는 공식 deepagents monorepo 전체 checkout이다. 개발용 에이전트의 cwd는 `deepagents/libs/code/`다. `deepagents_code/cyrano/`는 우리가 개발할 제품 코드이며 dcode base 자체가 아니다. `cyrano/`는 설계·개발·실행·참고·검증 지원 자료다. dcode 원본 `pyproject.toml`, `uv.lock`, `deepagents_code/__init__.py`를 Cyrano 파일로 대체하지 않는다.

현재 배포 ZIP의 `copy_to_dcode/` **내용**을 `libs/code/`에 병합한다. ZIP root의 prepare/verify/tests는 복사 보조와 포장 검사 전용이며 실행 프로젝트 밖에 둔다. 이미 수정한 파일이 있으면 diff를 검토하며 무조건 덮어쓰지 않는다. 현재 확인한 소스 기준은 `7f9e8ed3a555933902045792da9bb184950ee7b2`; 이후 버전은 별도 호환성 검사 없이 승인하지 않는다.

## 2. 준비

깨끗한 전체 clone의 원하는 개발 브랜치에서 먼저 dcode의 DEVELOPMENT.md를 읽는다. 저장소가 달라졌으면 조사 기준과 비교한다. 인터넷·패키지 설치 권한을 확인한 뒤 `libs/code`에서 `uv sync --group test` 또는 공식 `make bootstrap`을 실행한다. bootstrap은 git hooks도 설치하므로 허가 범위를 확인한다. 원본 native smoke/lint/test 결과와 환경을 기록한다. 기존 실패를 새 기능의 성공으로 바꾸지 않는다.

Cyrano를 병합한 뒤 다음은 현재 실행 가능한 준비 검사다.

```bash
python cyrano/scripts/dev.py check
python cyrano/scripts/dev.py schemas
python cyrano/scripts/assessment.py validate
python cyrano/scripts/doc_route.py --task WP00 --stage plan --content
```

`check`의 기반 테스트와 schema 검사는 실제 dcode 권한·Memory 효과·provider cache 시험이 아니다. dependency가 없으면 해당 검사는 blocked다.

## 3. AI 개발 시작

`libs/code`를 IDE/terminal cwd로 열고 설치되어 있는 coding assistant를 실행한다. 먼저 `AGENTS.md`, `cyrano/AGENTS.md`, `cyrano/IMPLEMENTATION_REQUEST.ko.md`를 읽힌다. 전체 FULL_DESIGN이나 참고팩을 한꺼번에 주입하지 않는다. 할당 WP의 선행 작업을 확인하고 `doc_route.py --task <ID> --stage plan`으로 필요한 문서를 선택한다.

1. 현재 요구·범위·완료 조건을 확정한다. 기존 인터뷰 답변은 현재성·scope를 확인해 재사용하고, 알 수 있는 내용을 다시 묻지 않는다.
2. 변경 파일·순서·생산/소비 인터페이스·테스트·비용·복구를 계획한다.
3. 독립 AI 리뷰가 구체적인 finding을 만들고, 수정 또는 반증 뒤 다시 판정한다.
4. 개발자의 변경 허가 뒤에 코드를 수정한다. 제품 계획 승인과 실행 허가 구현 전에는 advisory 개발 환경임을 명시한다.
5. 사례 명세를 읽고 거부/오류 테스트부터 작성한다. 권한·프로세스 경계의 fake를 실제 차단 증거로 쓰지 않는다.
6. 단계별 검증 뒤 변경한 설계·계약·fixtures·문서목차를 갱신한다.
7. 범위·acceptance·external effect가 달라지면 다시 계획·리뷰·승인한다. 승인된 후보 lineage 안의 정상 코드 수정마다 전체 인터뷰를 되풀이하지 않는다.

## 4. 문서·계약 갱신

```bash
python cyrano/scripts/dev.py docs
python cyrano/scripts/doc_route.py --task WP09 --stage implement --content
python cyrano/scripts/case_route.py --task WP09
python cyrano/scripts/dev.py check
```

`docs`는 기존 WP/TS/RC/RF metadata에서 라우터·목차·통합본을 재생성한다. 수동으로 새 연구팩을 설치하거나 NG를 추가 등록할 단계는 없다. 한 파일의 계약을 수정하면 그 계약을 읽는 작업만 새 digest를 갖는다. 전체 catalog hash를 상시 prompt에 넣지 않는다.

## 5. 제품 시험 실행

할당 WP의 테스트 파일과 실제 dcode adapter가 구현된 뒤에 `uv run --no-sync python -m pytest tests/cyrano_product/<담당파일>.py -q`를 실행한다. 제품 시험에는 실행환경·source·suite·policy digest와 원시 결과가 필요하다. 0건 수집, 필수 skip, LLM의 완료 주장, fixture-only 통과는 제품 인수 증거가 아니다.

## 6. 중단·재개·원복

현재 작업 사본과 변경 diff를 보존하고 실제 실행 여부를 확인한다. timeout 이후 외부 변경이 불명확하면 unknown_outcome으로 남겨 확인한다. 사용자 수정 파일은 전달 receipt만으로 삭제하지 않는다. 중단된 승인 화면을 재개할 때 pending request ID와 nonce·display subject를 유지/검증하며 임의로 새 허가를 만들지 않는다. 원본 반영·데이터 rollback·publish는 별도 권한과 recipe를 따른다.

## 7. 완성 판정

15개 평가 항목40점은 실제 제품에서 채점한다. 현재 기본 점수표는 not_evaluated다. Memory 지속/실제 적용, before-after/회귀/다음 작업 반영, 전체 native trace/계수/오류 탐색, 승인 전 모든 변경경로 차단을 실험해야 한다. 문서·기반 검사 수를 제품 점수로 치환하지 않는다.
