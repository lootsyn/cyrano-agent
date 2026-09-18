# 현재 소스 구조

CYRANO는 `libs/code/deepagents_code/cyrano/`의 Python namespace다. contracts/kernel/sqlite/context/memory/interview/workflow/improvement/evaluation/plugins/dcode/events/cli의13개 기능 모듈을 갖는다. 기존 monorepo의 build backend와 wheel package `deepagents_code` 아래에 위치하지만 runtime JSON/SQL resource packaging과 실제 dcode activation은 아직 검증되지 않았다.

[Native 배치와 목표 연결](design/DCODE_INTEGRATION.ko.md), [평가 전략](testing/STRATEGY.ko.md), [기존 상세 결정](design/architecture/2026-09-16-system-design.ko.md)을 함께 읽는다. 현재 배치·toolchain·사용자 15항목 rubric을 단일 기준으로 사용한다. 기능과 보호 계약은 축소하지 않는다.

`cyrano/`는 설계·계약·agent 설정·scripts·reference를 소유하고 runtime 소스는 sibling namespace에 둔다. `tests/unit_tests/cyrano/`는 실제 순수기반 테스트이며 `tests/cyrano_product/`는 향후 실제 dcode·격리·live assessment를 구현할 위치다. root의 native `pyproject.toml`, `uv.lock`, `Makefile`, CLI 및 상위 source는 이 추가 배치로 바뀌지 않는다.

현재 runtime adapter는 계약과 진단용이며 실제 live graph에 자동 등록되지 않는다. 주 실행자의 승인·evaluation 권한을 Python module visibility나 prompt instruction 하나로 보호했다고 주장하지 않는다. target 소스는 broker/execution isolation에서 제한하며 고객 repo는 설치 때문에 오염시키지 않는다.
