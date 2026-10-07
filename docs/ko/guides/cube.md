---
title: Cube 연결
description: 이미 운영 중인 Cube를 Decision Layer에 연결합니다.
---

# Cube 연결

Decision Layer는 Cube의 데이터베이스를 직접 연결하거나 지표 정의를 다시 만들지 않습니다. 운영 중인 Cube의 REST API를 사용합니다.

## 연결하기

샘플 Cube는 `examples/complete-journey`에서 `docker compose -p decision-layer-cube up -d --build --wait --wait-timeout 900`으로 실행합니다. [dbt MetricFlow 예제](./metricflow.md)는 같은 데이터를 사용하는 별도 선택지입니다. 아래는 이미 운영 중인 Cube를 연결하는 방법입니다.

1. 저장소 루트에서 `docker compose up -d --build --wait`를 실행하세요.
2. [Sources](http://localhost:3000/sources)를 여세요.
3. Cube API URL과 인증 방식을 입력하고 **연결 테스트**를 누르세요.
4. 연결되면 **Metrics**에서 지표와 차원을 확인하세요.

Docker 안의 API가 컴퓨터에서 실행되는 Cube에 접근한다면 URL은 보통 `http://host.docker.internal:4000/cubejs-api/v1`입니다. 원격 Cube는 해당 서버의 전체 API URL을 입력하세요. 컨테이너 안에서 `localhost`는 그 컨테이너 자신입니다.

URL만으로 연결되는지는 Cube의 인증 설정에 달려 있습니다. 운영 환경에서는 Cube가 발급하고 검증하는 사용자 토큰을 사용하세요. 개발용 API secret 방식은 로컬 테스트용입니다. 화면에서 저장한 비밀값은 암호화되고 환경변수 설정이 우선합니다.

연결 실패 시에는 URL에 `/cubejs-api/v1`이 포함됐는지, API 컨테이너에서 접근 가능한 주소인지, 사용자의 토큰에 모델 접근 권한이 있는지 확인하세요.

자세한 옵션과 포트 변경은 [영문 연결 가이드](/guides/cube)를 참고하세요. 다음 단계는 [Recipe 만들기](./recipes.md)입니다.
