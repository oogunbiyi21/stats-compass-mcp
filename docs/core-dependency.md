# How stats-compass-mcp depends on stats-compass-core

**Decided 9 October 2026, from 0.3.33: a compatible range,
`stats-compass-core[all]>=0.1.40,<0.2`.** Until 0.3.32, each release pinned one
exact core version.

## Why

- **Exact pins coupled the releases.** Every core release, even a patch, needed
  an mcp release that only moved the pin, and with it a second go from the
  founder.
- **It blocked an urgent fix.** core 0.1.40 fixes a memory exhaustion that was
  live on the hosted server (re-scan F6). With mcp 0.3.32 pinning
  `==0.1.39`, hosted could not install it until mcp released too.
- **Reproducibility is hosted's to keep.** Hosted pins both packages, so a
  deployment does not change unless hosted moves its pins on purpose.
- **This is an MVP.** Shipping fixes comes first. The policy can tighten again
  when there are paying users to protect from surprise upgrades.

## What the range promises

- Core follows semantic versioning within 0.1.x: a patch release does not
  change a tool's inputs or remove a tool.
- The lower bound is the first core version this mcp release needs. 0.3.33
  needs `FROM_ENVIRONMENT` and the 0.1.40 fixes.
- The upper bound stops at the next minor version, where breaking changes are
  allowed.

## When to revisit

- **A core 0.1.x patch breaks mcp.** Tighten to exact pins, and treat the break
  as a core bug.
- **Core 0.2 ships.** Release mcp with a new range after testing against it.
