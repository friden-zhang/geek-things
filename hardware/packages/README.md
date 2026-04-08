# Hardware Packages

Internal packages are organized by reuse boundary:

- `interfaces/`: buses, connectors, board-to-board interfaces, and test-point naming schemes
- `power/`: power entry, protection, regulation, supervision, and measurement blocks
- `common/`: reusable support circuits that are not interface- or power-specific

Package files should use `snake_case.ato` filenames and expose `PascalCase` modules or interfaces.
