# 테스트 위치

`test_foundation.py`와 `test_semantics.py`는 실행 가능한 stdlib unittest다. `fixtures/schema-cases.json`은 JSON 모양의 정상·거부 synthetic 예다. `acceptance/catalog.json`은 미래 product-level 실행 명세이며 실제 테스트 통과 목록이 아니다.

각 WP는 tests/test_wpXX_product.py를 작성한다. 미구현 테스트를 skip placeholder로 만들어 green을 얻지 않는다. scripts/run_tests.py는 0개의 테스트가 검색되면 명시 실패한다. 실제 provider가 필요한 검사는 허가·예산·key와 격리 환경이 있어야 한다.
