# Interface design

Web and documentation share `web/styles/tokens.css`. The palette follows
Heartcount's coral actions, neutral surfaces and cobalt data colors.

- Use coral for the primary action and selected graph node. Use the darker action
  token for readable small text and white-on-color buttons.
- Keep page backgrounds and navigation neutral. Green indicates successful
  validation only; it is not a section or product color.
- Use cobalt for data marks. A chart's colors must not imply significance or
  causality that the Method did not establish.
- Use whitespace and typography to group content. Reserve borders for controls,
  tables and framed tools such as the analysis graph or query viewer.
- Keep graph node dimensions stable. Full step purpose and evidence belong in the
  selected step detail; the node is a scannable summary.
- Put the question and recorded answer first. Keep Recipe registration visible and
  provide results, settings, queries and sources as peer tabs.

Check desktop and narrow mobile views with a real recorded Run. Verify graph
selection, keyboard tabs, Recipe registration and query copying after changes.
Do not introduce page-specific brand colors.
