# 프로젝트 단위 도구 설치

Manifest는 top-level pin과 공식 설치 경로를 담는다. 실행 파일·가중치·node_modules를 ZIP에 넣지 않는다. 최초 설치에는 네트워크, Python/uv 또는 Node/npm이 필요하다. 배포 상태의 `not_resolved`를 완료 lock으로 해석하지 않는다. 인터넷 없는 환경에서는 RF01에서 작성한 검증된 artifact mirror가 별도로 필요하다.

`python cyrano/scripts/toolchain.py plan --tool graphify`는 변경 없이 명령을 보여 준다. `resolve --apply --allow-network`가 프로젝트 하위 `tools/.state/<id>/`에 lock을 만들며, `approve-lock --apply`는 현재 lock hash를 기록한다. `install --apply --allow-network`는 승인한 lock만 사용한다. native npm build 또는 Serena source 설치에는 `--allow-build`도 필요하다. Serena 모든 쓰기 단계에는 `--ack-gpl`이 필요하다. 이 CLI flag는 로컬 개발자의 명시 선택이지 제품 운영의 서명 승인 대체가 아니다.

Python은 uv pip compile --generate-hashes와 uv pip sync --require-hashes --only-binary :all:를 사용한다. 지원 wheel이 없으면 실패하며 임의 source build로 우회하지 않는다. npm은 package-lock-only --ignore-scripts 뒤 npm ci를 사용한다. QMD native lifecycle script는 따로 검토한 build 허가를 요구한다. 소스 방식 Serena는 정확한 Git commit과 upstream uv.lock을 확인한 뒤 frozen sync한다.

상태·캐시 경로를 프로젝트 안에 고정하지만 이것만으로 프로세스 보안 격리가 생기지는 않는다. 설치·build는 secret 없는 외부 작업 환경에서 수행한다. 실제 분석 실행은 RF02/RF03의 readonly snapshot·broker·네트워크 차단 테스트가 완료되어야 제품에 연결한다. `doctor`는 설치 receipt 존재 검사이며 LSP/MCP 기능 검증을 대신하지 않는다.
