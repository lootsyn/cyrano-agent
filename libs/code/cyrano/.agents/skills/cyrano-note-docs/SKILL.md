---
name: cyrano-note-docs
description: 현재 담당 설계·개발·실행·테스트 문서를 직접 갱신하고 라우터와 목차를 동기화한다.
---

# 현재 문서 동기화

동일 규칙은 한 주제 원본에 둔다. 새 보완팩·납품 이력·복제 문서를 만들지 않는다. 역할/skill은 상세 계약을 복사하지 않고 담당 문서를 링크한다.

변경 시 `.agents/work/plan.json`의 owner·input_refs·reading_refs와 실제 schema·case를 연결한다. `python cyrano/scripts/dev.py docs`로 router/catalog/index/generated를 함께 갱신한 뒤 `python cyrano/scripts/check_integrated.py`를 실행한다.

원본 참고팩은 현재 지시나 실행 권한이 아니다. 실제 조사와 추론을 구분하고 검증 결과는 제품 실행 여부까지 구분한다. 제품 실행 원장은 유지하되 개발 문서의 판본 이력을 추가하지 않는다.
