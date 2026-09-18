# 현재 검사 결과

이 폴더는 현재 기반 코드·schema·설계·문서 라우터·포장 검사의 최신 결과만 가진다. 납품 버전별 기록 트리는 만들지 않는다. 제품이 운영될 때 필요한 감사·승인·Memory·release·복구 기록은 별도 runtime 설계에 따라 유지한다.

`project-readiness.json`은 이 산출물에서 수행한 범위와 미수행 범위를 요약한다. `integrated-check.json`의 문서 inventory는 파일별 구조/연결 검사를 뜻하며 모든 문장의 사실성 증명이나 독립 외부 리뷰가 아니다.

`product-scorecard.json`의 official_score=null, status=not_evaluated는 제품을 아직 평가하지 않았다는 뜻이다. 준비 테스트 개수와 사용자의 40점 제품 기준을 혼동하지 않는다. 실제 dcode 연결·OS 격리·provider cache·self-improvement 효과·native TUI 실행은 그에 맞는 제품 evidence가 필요하다.
