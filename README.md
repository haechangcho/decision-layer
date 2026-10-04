# Decision Layer

[English](README.md) · [한국어](README.ko.md) · [Docs](docs/README.md) · [Contributing](CONTRIBUTING.md)

**Make your team's analytical knowledge executable.**

Decision Layer turns your team's analytical knowledge into reusable **Recipes**. Web and AI clients execute the same procedures using semantic metrics and registered analytical **Methods**. Every **Run** keeps the question, results and evidence.

![A business question follows a reusable Recipe, executed through Web or AI with recorded evidence](docs/assets/decision-layer-overview.png)

## Try it

Start the sample data and local application with Docker Compose.

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer/examples/complete-journey
docker compose up -d --build --wait
```

Open [localhost:3000](http://localhost:3000). The first start downloads the sample data and can take a few minutes.

## Go further

- [Connect Claude or Codex through MCP](docs/guides/mcp.md)
- [Connect your semantic layer](docs/guides/cube.md)
- [Explore the sample and its data](examples/complete-journey/README.md)
- [Develop, test or add a Method](docs/README.md)

Web, Python, REST and MCP share one execution engine. AI clients choose registered Methods and Recipes; they do not run generated analysis code. The default installation is for local development.

[Apache 2.0](LICENSE)
