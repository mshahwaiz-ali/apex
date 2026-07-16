# Apex Documentation

This directory is organized by subsystem. Document names describe their purpose rather than internal milestone codes.

## Core context and status

- [Background information](background_information/README.md)
- [Implementation progress](progress/implementation_progress.md)
- [Spot workflow progress](progress/spot_workflow_progress.md)

## Subsystems

- [Futures analysis and quality](futures/)
- [Spot analysis](spot/)
- [Historical backtesting and datasets](backtesting/)
- [Paper trading](paper_trading/)
- [Funded-account readiness](funded/)
- [Validation evidence](validation/)
- [Operations](operations/)
- [Calibration](calibration/)
- [Reference commands](reference/)
- [Archived plans and handoffs](archive/)

## Naming policy

- Use lowercase `snake_case` filenames.
- Use descriptive subjects instead of milestone prefixes such as `S1`, `N4`, or `P1`.
- Keep operational instructions separate from architecture and implementation-status documents.
- Keep durable context under `background_information/`.
- Preserve obsolete or superseded material under `archive/` rather than mixing it with active documentation.
