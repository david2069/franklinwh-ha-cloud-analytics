# franklinwh-ha-cloud-analytics

Shared by the FranklinWH Direct Connect bridge and the Modbus bridge. Plan: direct-connect-bridge #215 (phases 1–2) and #504 (phases 3–4), approved 2026-11-07.

- FranklinWH cloud access only through the franklinwh-cloud library; no raw endpoint calls. Follow its rate limits and good-citizenship guidance.
- Never retry a login after code 400. Never log, store or commit credentials or tokens; the bridge passes them in and keeps them.
- Carry each field's evidence rating (CONFIRMED / CORROBORATED / INFERRED) from the library's field dictionary; show INFERRED as such. Never guess a value; a period with no data is null, never 0.
- Times in the gateway's site zone. Signs as the bridges use them: grid import +, export −; battery discharge +, charge −.
- The bridge owns credentials, routes and its database. This package owns the cloud calls, the payload, and a dependency-free page panel the bridge mounts.
- Don't copy FWHAI's history calls (known defects); FWHAI's Reporting tab is the UI model only.
- Branch and PR for every change; never commit to main. Every change has a test that fails without it.
- Public repo: no serials, IPs, emails, hostnames or tokens in code, tests, docs or commits.
