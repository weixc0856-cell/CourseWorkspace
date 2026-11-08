# Contributing

## License of contributions

This repository is dual-licensed: AGPL-3.0-or-later for the public open-source
edition, and a separate commercial license from the project owner for parties
that cannot accept AGPL obligations.

To keep that model possible, every contributor must sign the project CLA before
a pull request is merged; contact the project owner for the current CLA text.
The CLA grants the project owner a perpetual,
worldwide, non-exclusive, royalty-free, irrevocable right to use, reproduce,
modify, distribute, sublicense and relicense the contribution under
AGPL-3.0-or-later and under other terms, including a commercial license.

Do not submit code you cannot license this way. Third-party code must keep its
original license and be added to NOTICE.

## Before a pull request

```powershell
.\scripts\check.ps1
.\scripts\check-paths.ps1
```

- Do not add real course content, build outputs, runtime state, model weights,
  API keys, or machine-specific paths.
- Keep `docs/archive/**` out of the remote; only `docs/archive/README.md` is
  tracked.
- Update tests and the relevant docs when behavior changes.
