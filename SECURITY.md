# Security Policy

This server handles mailbox credentials and untrusted mail content, so security reports are taken seriously.

## Reporting a vulnerability

Please do **not** open a public issue. Use GitHub's private
[security advisory](https://github.com/KonstiJo/sogo-mail-mcp/security/advisories/new) form instead.
Include steps to reproduce and the affected version. You can expect a first reply within a few days.

## Scope

Of particular interest: prompt-injection paths that lead to sending or permanently deleting mail,
IMAP command injection through tool arguments, and credential leakage.
