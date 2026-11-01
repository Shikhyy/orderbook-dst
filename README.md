# OrderBook-DST

**TL;DR (10 lines)**

OrderBook-DST measures whether AI models write correct trading-system code.
The eval has 8 tasks in 5 families.
Each task asks a model to implement one engine rule.
The grader checks three tiers: visible unit tests, a targeted trace, and 20 hidden random traces.
All four invariants (I1–I4) must hold after each event.
Two variants per family show the effect of coupling: variant A is a pure function, variant B changes engine state.
The reference engine is a pure-Python exchange. It uses integer arithmetic only.
Run `make validate` to check all reference solutions and mutants. No API key is needed.
Run `make regrade` to re-score stored outputs. No API key is needed.
See the sections below for judge, developer, and finance entry points.

## Entry points

- **Judge:** See the Results section and the Failure Cards section.
- **Developer:** See the Architecture section and run `make setup && make validate`.
- **Finance reader:** See the Glossary section and docs/04_RULEBOOK.md.

## Architecture

See `docs/03_ARCHITECTURE.md` (in the pack, not committed).
The main module is `exchange_core/engine.py`.
The grader is `graders/dst_grader.py`.

## Results

*Populated after M8.*

## Failure Cards

*Populated after M9.*

## Glossary

*Populated after M9.*

## AI Use

See `AI_USE.md`.
