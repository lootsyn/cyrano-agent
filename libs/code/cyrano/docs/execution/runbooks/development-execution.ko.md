# 통합 개발 실행 안내

유형: 개발 tutorial. Python3.12이상과 저장소 사본이 필요하다. paid 모델·dcode 설치·고객코드 수정은 이 준비검사의 전제가 아니다.

## 1. 검사

```sh
python cyrano/scripts/dev.py status
python cyrano/scripts/dev.py check
python cyrano/scripts/dev.py schemas
python cyrano/scripts/check_integration.py
python cyrano/scripts/style_audit.py
python cyrano/scripts/dev.py quality
```

blocked/failed는기록하고먼저해결한다. schemas는jsonschema, quality는고정된Ruff/ty가필요하다. 이파일이설치나호출을자동허가하지않는다.

## 2. 할당

[통합 개발 실행계획](../INTEGRATED_WORK_DETAILS.ko.md)을 읽고 `.agents/work/plan.json`에서 선행이verified인 WP를선택한다. 초기WP는외부사람검토로시작한다. owner영역·exact변경계획·실행명령·권한·rollback을review받고 작업한다.

## 3. 구현·문서 갱신

소유WP의함수와수용ID를구현한다. v1을덮어쓰지말고registry가선택한버전을검증한다. role/skill은필요한내용만로딩하고 제품skill을변경했다면resource/contentdigest도갱신한다. 원본references는수정하지않는다.

```sh
python cyrano/scripts/dev.py docs
python cyrano/scripts/dev.py check
python cyrano/scripts/dev.py schemas
python cyrano/scripts/check_integration.py
```

## 4. 인수

실제검사와최종postimage로독립결과리뷰를받는다. `.agents/work/plan.json`의completion_evidence경로에보고서를기록한다. unresolved/unknown/qualityblocked를안고verified로바꾸지않는다. `evidence/product-scorecard.json`은실제품증거없이는채점하지않는다.

## 5. 재압축

```sh
python cyrano/scripts/package.py --output /absolute/output/cyrano-project.zip
```

출력경로는실제원하는저장위치로정한다. `.venv`, cache, git metadata, 비밀환경파일은package에서제외된다. 압축해제한새사본에서 check/schema/integration을다시실행한다. generateddoc와원본source의hash는일치해야한다.

## source-native 재압축 범위

`cyrano/scripts/package.py`는 `deepagents_code/cyrano`, 개발 자료, Cyrano 테스트, 짧은 발견용 skill을 함께 묶은 **code-root 추가분 ZIP**만 만든다. 이전처럼 개발 문서 폴더만 묶지 않는다. native dcode base와 승인 후 수정한 native 파일은 이 추가분에 포함되지 않으므로, 실제 제품 fork 전체를 납품할 때는 검토된 Git commit과 전체 monorepo export/patch를 별도로 만들고 원본·의존성·라이선스·native diff를 포함해야 한다. source export는 secret 파일명 screening일 뿐 내용 검사·운영 release 서명을 대신하지 않는다. 사용자 runtime DB·secret·실제 run payload는 배포하지 않는다.
