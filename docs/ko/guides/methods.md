---
title: Method 기여하기
description: 검증 가능한 분석 기능을 공통 실행 엔진에 추가합니다.
---

# Method 기여하기

Method는 입력, 실행 조건, 결과 형식이 정해진 분석 기능입니다. 기존 Method를 다른 순서나 설정으로 쓰는 것만 필요하다면 [Recipe](./recipes.md)를 만드세요.

## 시작할 코드

[실행 가능한 기여 템플릿](https://github.com/haechangcho/decision-layer/tree/main/examples/method-template)에는 Method 계약과 독립 테스트가 있습니다. Method는 검토한 Python 코드로 서버에 설치됩니다. 웹에서 사용자 코드를 올리거나 AI가 생성한 코드를 실행하지 않습니다.

1. `src/decision_layer/methods/` 아래에 모듈을 추가합니다.
2. Manifest에 이름, 버전, 입력 역할, 파라미터, 결과와 해석 범위를 선언합니다.
3. `ctx.dataset(DatasetSpec(...))`으로 필요한 데이터 단위와 열을 요청합니다.
4. 결과, 검증, 경고와 실행 근거를 반환합니다.
5. 누락 입력, 작은 표본, 지원하지 않는 가정, 알려진 결과에 대한 테스트를 추가합니다.

지표 SQL, 조인과 접근 권한은 Cube에 남겨야 합니다. 통계·ML 라이브러리는 사용할 수 있지만 의존성과 버전을 명시하고, 데이터 추출 한계와 해석 조건을 테스트해야 합니다.

전체 계약과 코드 링크는 [영문 Method 가이드](/guides/methods)에 있습니다.
