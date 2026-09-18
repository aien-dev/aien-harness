# Contributing to aien-harness

We welcome contributions from sovereign systems engineers and developers passionate about autonomous agent infrastructure.

## Sovereign Principles & Invariants

All contributions must adhere to our engineering invariants:
1. **Unslop Standard**: Zero em dashes (`—`) or en dashes (`–`). Use standard punctuation (commas, colons, parentheses, periods). Forbid AI buzzwords ("delve", "tapestry", "game-changer", "beacon").
2. **Native Performance**: Prioritize native compiled code over interpreted runtimes. Eliminate unnecessary runtime overhead.
3. **Hardware Key Vault**: Never commit plaintext `.env` files, credentials, or private keys.
4. **Drop != Delete Upstream Rule**: Any modifications enabling consumer hardware compatibility must be structured for clean upstream contributions.

## Development Setup

### Building & Testing
```bash
# Clone the repository
git clone https://github.com/aien-dev/aien-harness.git
cd aien-harness

# Run verification suite
python3 server.py --test
```

## Pull Request Guidelines

1. **Branch Naming**: Use descriptive prefixes: `feat/`, `fix/`, `perf/`, `docs/`.
2. **Atomic Commits**: Keep commits focused and logically grouped. Follow Conventional Commits format (`feat(core): add validated schema parser`).
3. **Test Coverage**: Include tests for any new behaviors or bug fixes.
4. **Documentation**: Update documentation and examples when modifying public interfaces.
