# Complete Journey 데모 데이터

데모 데이터는 승인된 PostgreSQL의 `journey`, `journey_meta` 스키마에 적재합니다.
원본 8개 테이블을 사용하며 거래 데이터는 2,595,732행, 매출 기준값은
8,057,463.08입니다. 기존 DB를 사용하는 예외는 운영자가 적재 도구의 사전 검사와
계정 권한을 검토한 후 진행하고, 접속 정보와 적재 이력은 비공개로 보관합니다.
Cube에는 가급적 별도 읽기 계정을 사용합니다.

고객사에 별도의 DB와 계정을 만들 수 있다면 아래의 전용 DB 방식을 사용할 수 있습니다.

| 항목 | 이름 | 권한 |
|---|---|---|
| 데모 DB | `dl_demo_journey` | `dl_demo_loader` 소유 |
| 적재 계정 | `dl_demo_loader` | 데모 DB의 스키마·테이블 생성 및 적재 |
| Cube 계정 | `dl_demo_reader` | 데모 `journey` 스키마의 SELECT |

두 계정은 LOGIN만 허용하며 superuser·CREATEDB·CREATEROLE 권한이나
다른 역할 멤버십이 없어야 합니다. 기존 계정이나 비밀번호는 재사용하지 않습니다.
PostgreSQL의 `PUBLIC` 권한은 인스턴스의 다른 DB에도 적용될 수 있으므로,
관리자가 기존 DB의 PUBLIC 권한과 새 계정의 접근 가능 범위도 확인해야 합니다.
이 스크립트는 기존 DB의 권한을 바꾸지 않습니다.

## 1. 관리자의 전용 DB 생성

관리자가 `CREATEDB`, `CREATEROLE` 및 새 DB 소유자 지정 권한을 가진 계정으로
[provision.sql](provision.sql)을 실행합니다. 두 비밀번호는 각각 32자 이상이며
서로 달라야 합니다. 아래 변수는 **예시 이름만** 표시하며 실제 값은 안전한 환경에서
설정합니다. 관리자 비밀번호는 `.pgpass`/`PGPASSFILE` 등으로 관리합니다.

```bash
# 관리자 쉘에서 두 변수를 안전하게 입력한 후 실행
export DL_POC_LOADER_PASSWORD DL_POC_READER_PASSWORD
psql -X -v ON_ERROR_STOP=1 -h <postgres-host> -U <admin-user> -d postgres \
  -f deploy/poc/journey/provision.sql
unset DL_POC_LOADER_PASSWORD DL_POC_READER_PASSWORD
```

DB 또는 역할 이름이 이미 있으면 시작 전에 중단합니다. `CREATE DATABASE`는
트랜잭션 안에서 실행할 수 없으므로 도중에 실패하면 일부 역할이 남을 수 있습니다.
그 경우 자동 삭제하지 말고 상태를 확인한 뒤 관리자가 처리해야 합니다.
실행 로그나 셸 기록에 비밀번호를 남기지 않습니다.

## 2. 전용 적재 계정으로 적재 및 검증

원본은 기존 공식 Complete Journey zip입니다. SHA-256과 8개 CSV 헤더를 확인합니다.
인스턴스 디스크 여유와 백업 정책을 먼저 확인합니다. 원본은 약 128 MiB이며,
압축 해제된 테이블·인덱스·임시 작업 공간은 더 필요합니다.

```bash
# PGPASSFILE에 dl_demo_loader의 비밀번호를 별도 설정하고 파일 권한을 0600으로 제한
export PGPASSFILE=<secure-pgpass-file>
export DATABASE_URL=postgresql://dl_demo_loader@<postgres-host>:5432/dl_demo_journey
.venv/bin/python deploy/poc/journey/load_journey.py \
  --archive examples/complete-journey/data/complete-journey.zip
```

연결 DB·계정·소유자·역할 권한이 다르거나 기존 데이터의 import marker가 다르면
중단합니다. 새로운 적재는 하나의 DB 트랜잭션으로 처리하며, 같은 파일의 재실행은
행 수를 검증합니다. 적재 후 `dl_demo_reader`에만 조회 권한을 부여하고 독립 SQL로
매출·조인·날짜·캠페인 파생값을 검사합니다. 실제 환경의 권한/네트워크는 별도 확인이
필요합니다.

검증이 끝나면 새 heartcube에는 `dl_demo_reader` 접속값만 설정합니다. 관리자와
적재 계정 비밀번호를 앱 또는 Cube 런타임에 전달하지 않습니다.
