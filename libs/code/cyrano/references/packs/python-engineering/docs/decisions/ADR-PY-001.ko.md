# ADR-PY-001 — UDH의 Python 품질 정책 정합화

상태: PROPOSED_FOR_IMPLEMENTATION. 사용자 저장소에 반영되거나 승인된 것으로 간주하지 않는다.

배경: 이전 설계 문서는 PEP8 기본 79/72를 선언했지만 후속 프로젝트 pyproject는 Black 88,
Ruff E501 ignore, mypy strict, Python 3.12를 사용한다. 앞선 대화의 Pyright/Python3.11 예시는
일반 대상 repo 예제다. 값들을 조용히 혼합하면 구현 모델이 다른 정책을 만들게 된다.

결정 제안: UDH 자체는 기존 Python3.12/Black/mypy를 유지한다. `team88-doc72`라는 명시적
team profile을 사용하고, W505/max-doc-length=72와 naming/docstring 검사를 도입한다.
E501 ignore 해제는 before inventory/baseline 검토 후 적용한다. 기존 code가 많으면 별도 migration
작업으로 수행한다. Pyright는 기존 대상 repo가 사용하는 경우의 adapter로 지원한다.

결과: 기존 UDH 구조를 존중하면서 PEP8 기본값과 팀 합의 예외를 구분한다. 순수 formatter 통과를
전체 PEP8/정확성 증명으로 부르지 않는다. 품질 정책 변경은 보호된 변경 표면으로 관리한다.

검증: PY-W01 승인 → PY-W04 config guard → PY-W05/W06 actual tool compatibility → legacy
migration → CI required check 설정. 승인 및 실제 적용이 끝나기 전에는 IMPLEMENTED로 바꾸지 않는다.
