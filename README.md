# Decision Layer

[English](README.md) · [한국어](README.ko.md) · [Docs](docs/README.md) · [Contributing](CONTRIBUTING.md)

**Make your team's analytical knowledge executable.**

Decision Layer connects governed metrics to analytical **Methods** and reusable **Recipes**. Web and AI clients run the same procedures; every **Run** keeps the question, result and evidence. Cube owns metric definitions and data access.

![A semantic metric, analysis methods and a recorded run](docs/assets/decision-layer-overview.png)

## Try it

Docker with Compose is required. The sample starts PostgreSQL, Cube, the API and Web with an empty Recipe library.

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer/examples/complete-journey
docker compose up -d --build --wait
```

Open [localhost:3000](http://localhost:3000). The first start downloads the sample data and can take a few minutes.

## Go further

- [Connect Claude or Codex through MCP](docs/guides/mcp.md)
- [Connect your own Cube](docs/guides/cube.md)
- [Explore the sample and its data](examples/complete-journey/README.md)
- [Develop, test or add a Method](docs/README.md)

Web, Python, REST and MCP share one execution engine. AI clients choose registered Methods and Recipes; they do not run generated analysis code. The default installation is for local development.

[Apache 2.0](LICENSE)
