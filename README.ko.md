# Decision Layer

[문서](https://decision-layer-docs.vercel.app/ko/) · [English](README.md)

**팀의 분석 노하우를 반복해서 실행합니다.**

Decision Layer는 semantic layer의 지표를 등록된 분석 방법(**Method**)과 재사용 가능한 분석 절차(**Recipe**)로 연결합니다. 웹이나 AI 도구로 분석하고, 실행 기록(**Run**)에서 질문·단계·근거를 확인한 뒤 팀이 다시 쓸 절차로 저장합니다.

웹, Python, REST, MCP는 하나의 실행 엔진을 사용합니다. AI 도구는 등록된 Method와 Recipe를 선택하며 임의로 만든 분석 코드를 실행하지 않습니다.

![비즈니스 질문을 Recipe로 분석하고 웹과 AI에서 같은 절차와 실행 근거를 재사용합니다](docs/assets/decision-layer-overview.png)

## 시작하기

Docker와 Compose를 설치한 뒤 샘플 데이터와 로컬 앱을 실행하세요.

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer/examples/complete-journey
docker compose up -d --build --wait
```

[localhost:3000](http://localhost:3000)을 여세요. 첫 실행에는 샘플 데이터를 내려받으므로 몇 분이 걸릴 수 있습니다.

예제에는 semantic layer가 연결되어 있고 Recipe는 비어 있습니다. 데이터 설명과 종료 방법은 [샘플 안내](examples/complete-journey/README.ko.md)를 참고하세요. 이 환경은 운영 배포용이 아닌 로컬 개발용입니다.

## 첫 분석 해보기

1. [Claude·Codex에 MCP를 연결하세요](https://decision-layer-docs.vercel.app/ko/guides/mcp).
2. “전체 데이터에서 수취액이 가장 큰 상품 부문은 어디야? 분석 단계와 근거도 남겨줘.”라고 질문하세요.
3. 웹의 **Runs**에서 분석을 검토하고, 단계와 설정을 그대로 **Recipe로 등록**하세요.

첫 분석에는 Recipe가 없어도 됩니다. AI 도구가 등록된 Method로 분석할 수 있습니다.

조직의 데이터로 분석하려면 [semantic layer를 연결하세요](https://decision-layer-docs.vercel.app/ko/guides/cube). 반복할 분석 절차는 [Recipe 안내](https://decision-layer-docs.vercel.app/ko/guides/recipes)를 참고하세요.

## 개발과 기여

[개발 환경](https://decision-layer-docs.vercel.app/ko/guides/development) · [테스트](https://decision-layer-docs.vercel.app/ko/guides/testing) · [Method 추가](https://decision-layer-docs.vercel.app/ko/guides/methods) · [아키텍처](https://decision-layer-docs.vercel.app/ko/ARCHITECTURE) · [기여 안내](CONTRIBUTING.md)

[Apache 2.0](LICENSE)
