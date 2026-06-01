# Security Policy

## Scope

This project exposes a public API backed by scraped and organized question-paper metadata. Security issues are taken seriously, especially around API keys, deployment config, scraper behavior, and data integrity.

## Do Not Share Publicly

Do not include real API keys, deployment secrets, private logs, private staging data, or infrastructure credentials in issues, PRs, screenshots, or test fixtures.

## Sensitive Areas

Changes to these areas need careful review:

- API-key authentication
- rate limiting
- CORS configuration
- health and reload endpoints
- scraper target/scope changes
- data validation and categorization logic
- path handling and error messages
- structured logging and observability
- deployment configuration

## Local Development Guidance

Use development-only API keys and local environment files. Do not commit `.env` files, production keys, deployment credentials, generated secrets, or private operational logs.

## Reporting

Use GitHub private vulnerability reporting when available. If unavailable, open a minimal public issue asking for a private channel, without including sensitive details.