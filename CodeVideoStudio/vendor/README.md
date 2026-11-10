# Vendor

Single checked-in copies of third-party runtime libraries.

| file | upstream | version | licence |
| --- | --- | --- | --- |
| `three/three.module.js` | three.js | r160 | MIT |

`three.module.js` is copied into each `shots/<shot>/` directory by
`course-control vendor-sync` (and automatically before a `render:code_video`
capture). The per-shot copies are build inputs, not sources: do not edit or
commit them. Upgrade by replacing this file and re-running `vendor-sync`, then
re-capture the shots that use it.
