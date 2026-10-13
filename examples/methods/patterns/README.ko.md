# Method 개발과 직접 테스트

```bash
python3.11 -m venv .venv-method
.venv-method/bin/python -m pip install -c examples/methods/patterns/constraints-py311.txt -e '.[dev,stats,dowhy,econml]'
.venv-method/bin/python -m examples.methods.patterns --all
.venv-method/bin/python -m examples.methods.patterns.failures --all
```

[전체 시나리오](../../../docs/ko/guides/method-scenarios.md) · [작성 흐름](../../../docs/ko/guides/methods.md) · [고급 분석](../../../docs/ko/guides/statistical-methods.md)

`methods.py`는 실제 함수, `scenarios.py`는 독립 query·정답, `failures.py`는 실패 사례, `journey.py`는 실제 데이터·SQL 비교, `server.py`는 canonical API bootstrap, `explore.ipynb`는 선택적 실험입니다. 이 예제는 구현 코드이며 설계용 의사 코드가 아닙니다.
