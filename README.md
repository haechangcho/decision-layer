# Decision Layer

[Docs](https://decision-layer-docs.vercel.app/) · [한국어](README.ko.md) · [Quickstart](examples/quickstart/README.md)

**Teach your AI how your team analyzes data.**

Turn a reviewed analysis into a reusable playbook—with recorded steps, checks,
and evidence. Save the procedure once; apply it to a new period without copying
the previous answer. “Teach” means saving an executable Recipe, not training a model.

![A saved procedure selects Home in January, Grocery in February, and requests input for a March tie](docs/assets/recipe-replay.gif)

## See it work

The synthetic sample follows the highest-revenue department into its regions:

| Run | What happens |
| --- | --- |
| January | Home leads at 6,200; inspect Home's regions |
| Save | Register the analysis as a Recipe |
| February | The same Recipe selects Grocery at 6,720; inspect Grocery's regions |
| March | The departments tie; request input before selecting a branch |

These are live Cube queries through the normal execution engine. The walkthrough
is scripted and uses invented data; it is not an AI accuracy benchmark.

## Try it

With Node.js, Git, Claude Code and running Docker Compose v2:

```bash
git clone https://github.com/haechangcho/decision-layer.git
cd decision-layer
node scripts/install.mjs setup --client claude
```

Setup prepares the synthetic data, checks the replay and registers the MCP connection.
Restart Claude Code and ask the question below. **No local Python, MCP JSON or port
configuration.** Docker must stay running. First builds download dependencies and
can take several minutes. Web is optional: [inspect evidence](http://localhost:3100/runs).

Only want to inspect the product? Run `bash scripts/demo.sh` without Claude Code.
[Setup, removal and limitations](examples/quickstart/README.md) · [Larger retail sample](examples/complete-journey/README.md)

## Use it from your AI client

After setup, ask in Claude Code:

> Reuse the saved department investigation for February 2026. Find the leading
> revenue department, then break its revenue down by region. Explain the evidence
> and limitations.

[Copy the sample MCP configuration](examples/quickstart/README.md#ask-your-ai).
For your organization, connect [Cube](docs/guides/cube.md) or the
[official dbt Semantic Layer API](docs/guides/dbt.md).

## Why add this to a semantic MCP?

A semantic layer defines what metrics mean. Good instructions tell an agent how
to investigate. Decision Layer adds executable procedures: registered Methods,
validated inputs, explicit selection rules and recorded execution evidence.

- **Reuse the rule:** select this period's leading group, not last month's winner.
- **Inspect what ran:** retain Method versions, applied inputs, queries and warnings.
- **Handle missing evidence:** supported checks request input or refuse execution.
- **Keep one execution model:** Web, Python, REST and MCP use the same engine.

These checks do not guarantee an analytically correct answer. A flawed procedure
can still be wrong; statistical association is not proof of causation.
See the [evaluation protocol](docs/guides/evaluation.md) before making accuracy claims.

## How it works

**Method** = a registered analytical capability. **Recipe** = a reusable procedure.
**Run** = one recorded execution and its evidence.

Metric formulas, joins and permissions remain in the semantic provider. AI clients
select registered Methods and Recipes; generated analytical Python/SQL is not the
execution path. You can explore first and save a useful Run as a Recipe afterward.

## Contribute

Try a [small contribution](docs/guides/contribute-examples.md): an analytical edge
case, a reproducible example or an onboarding improvement.

To develop a Method, Python 3.11+ is enough:

```bash
make setup
make example
```

[Method guide](docs/guides/methods.md) · [Contributing](CONTRIBUTING.md) ·
[Development](docs/guides/development.md) · [Architecture](docs/ARCHITECTURE.md)

[Apache 2.0](LICENSE)

### Measured pilot

The first 18-trial pilot found higher token use, estimated cost and latency with Decision Layer. [Read the results, limitations and next actions](docs/guides/benchmark-pilot.md). Numeric agreement alone is not an accuracy claim.
