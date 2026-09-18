---
name: memory-curation
description: 실행 근거로 scoped memory나 skill의 부분 개선 후보를 만들 때 사용한다.
---

# memory-curation

현재 release와 근거·반례를 조회한다. add/refine/link/deprecate 단위로 최소 delta를 제안하고 적용/비적용 조건을 작성한다. protected instruction·scope·평가 기준을 변경하지 않는다. 실행 실패를 검증 생략으로 해결하지 않는다. active write 대신 candidate를 반환하고 B 경로는 실제 paired eval·독립 리뷰·승격·다음 run 적용을 요구한다.

이 파일은 절차 원본이다. referenced runtime tool은 검증·활성화된 capability가 있을 때만 사용한다. 모델 이름별 custom prompt를 만들지 않는다.
