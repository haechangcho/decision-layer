# 실행 시나리오

조회 형태와 고급 SDK 계약을 검증하는 예제입니다. 처음 Method를 만든다면
[입문 노트북](../../../docs/tutorials/methods/write_your_method.ko.ipynb)부터 시작하세요.

| 파일 | 역할 |
| --- | --- |
| `methods.py` | 고급 Method 구현 |
| `scenarios.py` | 예상 조회와 정답 데이터 |
| `__main__.py` | 준비된 데이터로 시나리오 실행 |
| `failures.py` | 잘못된 입력과 거절 사례 |
| `discovery.py` | Method 탐색 |
| `journey.py` | 실제 Cube 실행과 SQL 비교 |
| `server.py` | 실제 데이터 검증용 API 시작 |

```bash
.venv/bin/python -m examples.methods.scenarios --case by_group
.venv/bin/python -m pytest -q tests/examples/test_scenarios.py
```

추가 통계 패키지 설치와 실제 데이터 검증은
[시나리오 가이드](../../../docs/ko/guides/method-scenarios.md)를 참고하세요.
[실험 노트북](../../../docs/tutorials/methods/query_scenarios.ipynb)도 같은 코드를 사용합니다.
