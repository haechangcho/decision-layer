# Hands-on tutorials

Start with **Python Method authoring**: write a function, register it, select data
and inspect the result. It runs on prepared data without Cube or an AI connection.

| Notebook | Purpose |
| --- | --- |
| [Python Method authoring](https://github.com/haechangcho/decision-layer/blob/main/docs/tutorials/methods/write_your_method.en.ipynb) | Ranking and OLS with the ordinary Python authoring API |
| [Advanced Method contracts](https://github.com/haechangcho/decision-layer/blob/main/docs/tutorials/methods/advanced_method.en.ipynb) | Typed SDK, multiple inputs and native statistical functions |
| [Query scenarios](https://github.com/haechangcho/decision-layer/blob/main/docs/tutorials/methods/query_scenarios.ipynb) | Query shapes and known-answer checks |
| [First SDK Method](https://github.com/haechangcho/decision-layer/blob/main/docs/tutorials/methods/first_method.ipynb) | Class-based SDK and opt-in Cube connection |
| [Peer comparison](https://github.com/haechangcho/decision-layer/blob/main/docs/tutorials/methods/peer_comparison.ipynb) | Combining three queries |
| [PyWhy review](https://github.com/haechangcho/decision-layer/blob/main/docs/tutorials/methods/pywhy_review.ipynb) | Optional estimator experiments |

Open the notebooks from a repository checkout in Jupyter or VS Code. Use a kernel
with the checkout and the required extras installed; the introductory notebook needs
`stats`. Supporting Python code is under `examples/`, and automated notebook checks
are under `tests/examples/`.

Continue with [Method projects](../guides/method-projects.md) to use your functions
in the admin console and through MCP. See the [repository map](../guides/repository.md)
when contributing to the product itself.
