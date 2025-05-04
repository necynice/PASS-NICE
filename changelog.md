# Changelog: v1.0.1 -> v1.1.0

## v1.1.0 Updates
- 변수, 함수명을 camelCase를 사용하게 변경하였습니다.
- aiohttp -> httpx로 request module이 변경되었습니다.
- initSession Request가 2개 감소하였습니다.
- 모든 웹 요청에 예외 처리가 강화되었습니다.
- 통신사 선택시 Literal을 사용하도록 변경되었습니다.
- 주요 변수, 함수명이 변경되었습니다.

### New Features
- X

### Bug
- 특정 상황에서 발생하던 버그를 수정하였습니다. (통신사 관련)

### Performance
- v1.0.1 대비 **유의미한 속도 변화**
- : initSession Request 2 Step 감소
- : 전반적인 코드 리팩토링

## Migration Notes
- please install httpx module (`requirements.txt`)
- bug report : telegram @sunr1s2_0