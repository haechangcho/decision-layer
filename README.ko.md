# Decision Layer

[English](README.md) · [한국어](README.ko.md) · [문서](docs/README.md) · [기여하기](CONTRIBUTING.md)

**팀의 분석 노하우를 반복해서 실행합니다.**

Decision Layer는 팀의 분석 노하우를 재사용 가능한 **Recipe**로 만듭니다. 웹과 AI 도구는 semantic layer의 지표와 등록된 분석 방법(**Method**)으로 같은 절차를 실행하고, 각 실행(**Run**)에 질문·결과·근거를 남깁니다.

![비즈니스 질문을 Recipe로 분석하고 웹과 AI에서 같은 절차와 실행 근거를 재사용합니다](docs/assets/decision-layer-overview.png)

## 시작하기

Docker Compose로 샘플 데이터와 로컬 실행 환경을 함께 시작합니다.

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer/examples/complete-journey
docker compose up -d --build --wait
```

[localhost:3000](http://localhost:3000)을 여세요. 첫 실행에는 샘플 데이터를 내려받으므로 몇 분이 걸릴 수 있습니다.

## 다음 단계

- [Claude·Codex에 MCP 연결](docs/guides/mcp.md)
- [Semantic layer 연결](docs/guides/cube.md)
- [샘플 데이터와 환경 확인](examples/complete-journey/README.ko.md)
- [개발·테스트·Method 기여](docs/README.md)

웹, Python, REST, MCP는 하나의 실행 엔진을 사용합니다. AI 도구는 등록된 Method와 Recipe를 선택하며 임의로 만든 분석 코드를 실행하지 않습니다. 기본 설치는 로컬 개발용입니다.

[Apache 2.0](LICENSE)
