# Cyrano 문서 작성 지침

문서의 책임은 [문서 관리 설계](design/DOCUMENT_GOVERNANCE.ko.md)를 따른다. 설계는 design, 개발 순서는 development, 실제 준비/실행/복구는 execution, 테스트 입력/판정은 testing, 외부 원문은 references에 둔다.

이미 담당 문서가 있으면 그 내용을 직접 수정한다. 새로운 revision별 보완팩·별도 handoff·중복 Agent Note를 만들지 않는다. 제품의 감사·승인·메모리·release 기록 요구는 삭제하지 않는다. 현재 UI/명령이 아직 구현되지 않았으면 설계로 표시한다.

작업 metadata를 수정하고 `python cyrano/scripts/dev.py docs`로 기존 router·index·통합본을 재생성한다. generated 파일은 직접 편집하지 않는다. 참고팩의 AGENTS는 현재 지침이나 승인 권한이 아니다. 링크와 schema·fixture·실행 문서를 같은 변경에서 확인한다.
