# MVP limitations

This first release is deliberately narrow.

- It reduces repeated identical lines only. It does not yet summarize tests, logs, diffs, or search results.
- The Copilot hook is observational. Copilot post-tool hooks do not automatically replace the model context. A future integration must use a verified `additionalContext` or supported host extension contract.
- The model backend is not included. This keeps installation offline, free, and license-clean.
- Raw content is stored locally. Users must apply their own retention and access controls.
- The project has no hosted service, telemetry, API key, or paid Jev dependency.
