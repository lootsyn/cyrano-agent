# 새 skill 추가

이 절차는 코드·문서 변경의 순서다. 제품 의미와 권한은 소유 schema·note가 정의한다.

1. 기존 skill과 중복인지, 적용 scope와 trigger가 무엇인지 정한다.
2. plugins/cyrano/skills에 짧은 SKILL과 필요한 references/resources를 추가한다.
3. manifest template과 role catalogue를 수정한다. executable은 code change로 분류한다.
4. positive/negative/native load tests를 추가한다.
5. B actual evaluation과 approval 뒤 불변 release에 포함한다.

변경한 acceptance ID와 실제 evidence를 연결한다. generated FULL_DESIGN은 직접 편집하지 않는다.
