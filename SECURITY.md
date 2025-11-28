# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability in LogCost, please report it responsibly by emailing the maintainers instead of using the public issue tracker.

**Do not open public GitHub issues for security vulnerabilities.**

When reporting, please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if applicable)

The maintainers will acknowledge your report within 48 hours and work toward a fix.

## Supported Versions

Security fixes will be provided for:
- Latest release version
- Previous minor version

Older versions may not receive security patches.

## Security Practices

LogCost follows these security principles:

- Minimal dependencies (zero required dependencies for core functionality)
- No execution of arbitrary code or shell commands from user input
- Proper file permission handling and non-root execution in Docker
- Thread-safe operations with lock protection
