# Security Policy

## Supported Versions

The following versions of `aien-harness` are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take the security of `aien-harness` and sovereign agent infrastructure seriously. If you discover a vulnerability, please report it responsibly rather than opening a public issue.

### Reporting Channels
- **Email**: `aien@aienos.com`
- **GPG Key**: Available upon request or via public keyservers.

### What to Include in Your Report
1. Detailed description of the vulnerability and attack vector.
2. Minimal reproduction steps or proof-of-concept.
3. Affected modules or dependencies.
4. Suggested mitigation or patch if available.

### Response Timeline
- **Initial Response**: Within 24 hours.
- **Triage Assessment**: Within 48 hours.
- **Patch Release**: Coordinated disclosure within 14 days or earlier depending on severity.

### Sovereign Security Invariants
- Zero plaintext API tokens or keys on disk. All integrations must use hardware TPM vault or secure loopback credential injection.
- Loopback isolation: Daemons and internal IPC default strictly to `127.0.0.1`.
- Safe deserialization: Untrusted inputs are strictly schema-validated before processing.
