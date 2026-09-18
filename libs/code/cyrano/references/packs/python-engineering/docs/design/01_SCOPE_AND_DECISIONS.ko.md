# 1. 범위, 적용 순서, 확정 결정

문서 ID: UDH-PY-QH / 버전: 1.0.0-design / 기준일: 2026-09-16.

이 문서는 앞서 제안한 Python Engineering Skill, 실행 가능한 품질 정책,
quality gate, 자동 복구, CI, 증거, 제한적 자기개선을 **UDH/dcode에 추가할 구현 명세**다.
기존 UDH 전체 제품을 다시 설계하지 않는다. 여기의 `udh quality ...`, `udh_quality`,
완료 판정 서비스는 새로 구현할 인터페이스다. 이미 dcode에 존재하는 명령으로 오인하지 않는다.
계약 참조 코드와 fixture는 제공하지만, dcode 플러그인 또는 제품 런타임 구현 완료를 뜻하지 않는다.

## 1.1 목표

Python 변경 요청을 받으면 저장소 관례를 조사하고, 요구사항과 검증을 연결한 계획을 검토한 뒤,
허가된 범위에서 구현한다. 동일한 코드 스냅샷에 대해 formatter/linter/type checker/test/review를
실행하고, 검증된 결과 없이는 UDH 작업을 성공으로 확정하지 못하게 한다.

PEP 8은 스타일 지침이다. 타입 검사, 테스트, 보안, 설계 적합성은 별도의 품질 축이다.
Black PASS 또는 Ruff PASS를 “모든 PEP 8 지침과 프로그램 정확성의 완전한 증명”으로 표현하지 않는다.
PEP 8은 프로젝트 관례와 호환성을 중시하며, 기본 코드 79자·주석/docstring 72자와
팀 합의에 따른 코드 길이 확장을 구분한다. [S01]

## 1.2 기존 UDH와의 정합성

확인한 `UDH_Project_FULL_DESIGN.ko.md`의 현재 준비 workspace는 다음을 선언한다.

| 항목 | 유지할 값 |
|---|---|
| 제품 런타임 | Python `>=3.12,<4` |
| 패키지 구조 | uv workspace: `packages/*/*`, `apps/cli` |
| formatter | Black, line-length 88, py312 |
| 타입 검사 | mypy strict |
| 실행 식별자 | Workspace → Session/Run → WorkUnit → Attempt |
| 설정 위치 | UDH 구성은 `configs/`, wire 계약은 `contracts/` |
| 역할 원본 | 제품용은 `plugins/udh`, UDH 자체 개발용은 `.agents` |

선행 `UDH_FULL_DESIGN.ko.md`에는 79/72 기준도 존재하고, 이후 프로젝트 설정은 88과
`ignore=["E501"]`을 사용한다. 이 추가 명세는 **기존 프로젝트의 88자를 유지하면서 72자 문서행
검사와 필요한 lint 규칙을 명시적으로 도입**한다. 79/72로 조용히 되돌리거나, 기존 ignore를
아무 설명 없이 삭제하지 않는다. 도입 작업에서 ADR-PY-001을 승인하고 baseline을 평가한다. [U01–U03]

앞선 대화의 Python 3.11/Pyright 예제는 일반 대상 저장소용 예제다. UDH 자체의 Python 버전이나
mypy를 바꾸는 근거가 아니다. 대상 저장소가 Python 3.11/Pyright이면 그 도구를 유지한다.
`PolicyResolver`는 대상 저장소의 승인된 설정을 읽으며 모델명으로 설정을 분기하지 않는다.
타입 검사기는 한 policy에서 하나만 필수로 선정한다. 두 도구를 동시에 필수화하려면 별도 ADR이 필요하다.

## 1.3 규범적 결정

| ID | 결정 |
|---|---|
| PY-ADR-01 | Black을 유일한 formatter로 사용한다. Ruff는 lint/import만 담당한다. |
| PY-ADR-02 | 기본 프로파일은 `team88-doc72`; `pep8-79-doc72`는 명시적 승인 후 선택한다. |
| PY-ADR-03 | AGENTS에는 짧고 안정적인 규칙, Skill에는 개발 절차, pyproject에는 도구 설정을 둔다. |
| PY-ADR-04 | 모델은 구현·분석·제안을 담당하고 최종 gate 판정은 결정론적 서비스가 담당한다. |
| PY-ADR-05 | 필수 검사를 생략·실행 불가·파싱 실패한 경우 PASS를 만들지 않는다. |
| PY-ADR-06 | 검증 대상, 정책, 실행 도구, 계획, 검증 suite의 digest를 함께 고정한다. |
| PY-ADR-07 | legacy는 전체 진단을 보존한다. 새 위반 0과 기존 부채 0을 구분한다. |
| PY-ADR-08 | 자동 복구는 최초 구현 뒤 최대 3회, 외부 재시도는 최대 1회다. 무한 반복하지 않는다. |
| PY-ADR-09 | 품질 정책·baseline·예외·runner·CI 보호 규칙은 implementer가 임의로 약화하지 못한다. |
| PY-ADR-10 | Self-improvement는 관측 근거와 실제 비교 실행을 거친 후보 승격으로만 적용한다. |
| PY-ADR-11 | 네이티브 dcode Hook은 편의/피드백 계층이다. 성공 확정 권한을 대신하지 않는다. |
| PY-ADR-12 | 개발용 로컬 검사와 강제 가능한 governed 검사의 보증 수준을 명시적으로 구분한다. |

## 1.4 지원 수준

`local_advisory`: 로컬 dcode + Skill + 동일 정책의 로컬 gate. 실수 감소용이며, 같은 사용자 권한의
임의 shell이 설정과 결과를 바꿀 수 있으므로 변조 방지된 검증으로 부르지 않는다.

`governed`: 승인된 controller/runner를 후보 작업 디렉터리 밖에 설치하고, agent와 검사 코드는
격리된 candidate 환경에서 실행한다. 결과 저장·승인·완료 확정은 agent가 쓸 수 없는 controller에 있다.
이 명세의 제품 완료 기준은 governed다. 지원 환경을 확보하지 못하면 local_advisory로 표시하며
동일 수준이라고 광고하지 않는다.

초기 governed 기준 OS는 Linux sandbox다. Python 모듈·로컬 보조 CLI의 macOS/Windows 테스트는
별도 실행한다. Windows에서 프로세스 트리 종료/권한 격리를 검증하지 않았다면 governed 지원을
주장하지 않고 `UNSUPPORTED_ISOLATION_BACKEND`로 차단한다.

## 1.5 비목표와 변경 권한

특정 LLM의 성격에 맞춘 프롬프트/정책 하드코딩, 자율적인 생산 배포, 자동 commit/push,
무조건적인 전 저장소 리포맷, 모든 경고의 무분별한 오류 승격은 하지 않는다.
사용자의 명시적 요청 없이 의존성 전면 업그레이드, baseline 재생성, 규칙 해제도 하지 않는다.
질문이 필요하면 이미 알려진 설정을 재질문하지 않는다. 외부 인증이나 본질적 승인만 blocker로 남긴다.
