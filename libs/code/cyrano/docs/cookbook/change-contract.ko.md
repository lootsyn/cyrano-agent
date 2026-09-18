# 계약 변경

이 절차는 코드·문서 변경의 순서다. 제품 의미와 권한은 소유 schema·note가 정의한다.

1. owner schema와 모든 consumers·subject projection을 찾는다.
2. adjacent version/migration과 오류 semantics를 설계한다.
3. 정상·거부·semantic·authority tests를 추가한다.
4. 원본 reference는 보존하고 현재 docs/fixtures/producer/consumer를 갱신한다.
5. schemas·check·quality와 필요한 실제 통합을 실행한다.

변경한 acceptance ID와 실제 evidence를 연결한다. generated FULL_DESIGN은 직접 편집하지 않는다.
