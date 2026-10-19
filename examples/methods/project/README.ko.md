# 완성 Method 프로젝트

`workshop_project/methods/`에 Python과 Skill을 함께 둡니다.

- `rank/method.py`: `workshop_project.rank`, 고정 컬럼으로 순위 계산
- `ols/method.py`: `workshop_project.ols`, 컬럼 이름을 인자로 받는 OLS
- `metric_review/SKILL.md`: `workshop_project.metric_review`, 기록된 조회 지침

저장소 루트에서 준비된 Python 환경으로 실행합니다.

```sh
python -m decision_layer check --project examples/methods/project
python -m decision_layer list --project examples/methods/project
# 이 프로젝트로 API를 시작할 때 실행합니다.
python -m decision_layer serve --project examples/methods/project --reload
```

`list`에서 이름과 정의 파일 경로를 확인합니다. `check`는 등록 검사이며 분석
정확성 검증은 아닙니다. [노트북](../../../docs/tutorials/methods/write_your_method.ko.ipynb)에서 만든 순위 함수와 OLS를
프로젝트 파일로 저장한 예제입니다. Web과 MCP는 서버가 읽은 등록 목록을 봅니다.

새 프로젝트는 `decision-layer init my_team`으로 생성합니다. 프로젝트 안에서
`decision-layer new python <이름>` 또는 `decision-layer new skill <이름>`으로
정해진 파일을 만듭니다. 운영에서는 검토한 파일과 의존성을 배포하고
`DL_PROJECT_DIR`로 프로젝트 루트를 지정해 API를 재시작합니다.

[프로젝트 개발 가이드](../../../docs/ko/guides/method-projects.md)
