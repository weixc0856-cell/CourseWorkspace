# Asset scene specifications

The 3D pipeline has three levels, connected by files rather than one giant
`.blend`:

```text
Level 1  Asset library
         <content_root>/assets/3d/library.json
              ↓  ids only
Level 2  Environment / set
         environments/<place>.json
              ↓  environment reference
Level 3  Shot
         shots/<shot>.json
              ↓
         Blender builder → render → film assembly
```

- **Environment** owns terrain, sky, set dressing and lights. It is reusable.
- **Shot** owns camera, duration, frame count, render profile and output. It
  references exactly one environment.
- **Asset library** is the only place that knows where a model, texture, HDRI
  or heightmap lives. The builder never invents a path.

The AI planner writes JSON specs. The contract is the schemas here; the builder
is `scripts/build_asset_scene.py`. AI does not write arbitrary Python per shot.

## Files

| File | Purpose |
| --- | --- |
| `scene-spec.schema.json` | entry point: environment or shot |
| `environment.schema.json` | Level 2 set |
| `shot.schema.json` | Level 3 camera/render |
| `camera.schema.json` | camera templates and explicit keyframes |
| `terrain.schema.json` | heightmap, size, displacement, material |
| `render.schema.json` | profile, engine, samples, resolution, passes |
| `lighting.schema.json` | HDRI, world strength, atmosphere, sun/lights |
| `animation.schema.json` | camera reference + optional shot-level overrides |
| `asset_catalog.schema.json` | one `library.json` entry |
| `capabilities.json` | supported templates, engines, passes, profiles |
| `lighting.schema.json` | handwritten: HDRI/world/atmosphere/sun/lights |
| `animation.schema.json` | handwritten: camera reference + shot overrides |

`asset-scene-schema` regenerates the five Pydantic-backed schemas
(`environment`, `shot`, `camera`, `terrain`, `render`) plus `scene-spec`.
`lighting` and `animation` are maintained by hand because they are composition
contracts, not model classes.

## Commands

```powershell
# validate one spec against the asset library
uv run --project CourseControl course-control asset-scene-validate --spec <spec>.json --json

# regenerate the JSON Schemas after changing the Pydantic models
uv run --project CourseControl course-control asset-scene-schema --output shared/scene-specs

# build a blockout or hero shot
blender --background --factory-startup --python scripts/build_asset_scene.py -- `
  --spec <spec>.json --profile blockout
```

## Build modes

```text
--build environment   # build blends/environments/<place>.blend
--build shot          # link the environment blend, build blends/shots/<shot>.blend, render
--build inline        # legacy: merge environment into the shot and render
--build auto          # default: environment spec -> environment; shot with env blend -> shot
```

Environment blends hold `ENV`, `ENV_ASSETS`, `ENV_LIGHTS` and `AssetWorld`.
Shot blends link those collections and the world, and keep only their own
camera and shot lights. Library Overrides are not implemented yet.

## Build manifest and cache

Each Blender build writes `manifests/<shot>-<build-id>.json` and `.log` next to
the output (or under `--manifest-dir`). The manifest records hashes of the shot
spec, environment spec, library, builder, assets, Blender/Python/addons, render
parameters and the Visual Grammar file. A second build with identical inputs
prints `ASSET_SCENE_CACHED` and skips the render.

```powershell
scripts/render-asset-shot.ps1 -Spec <shot>.json -Profile preview `
  -ManifestDir <dir> [-NoCache] [-Frames 1]
```

The manifest is build evidence, not a release gate. See
`docs/v2/生产管线v0.2-P0交付记录.md`.

## Camera templates

`static_hold`, `dolly_in`, `dolly_out`, `pan`, `tilt`, `crane`, `orbit`,
`tracking`, `parallax`. A template expands to explicit keyframes in the builder:
hold → constant move → hold by default, so the camera does not ease for the
whole shot. `orbit` writes an arc; all other moving templates need
`location` and `end_location` (or `end_target` for `tilt`).

## Render passes

`render.passes` accepts `beauty`, `ao`, `depth`, `mist`, `normal`, `emission`,
`cryptomatte`; the builder writes a multilayer EXR under `render.pass_dir`
(default: `passes/` next to the output). This is for shot review and final
compositing; the H.264 preview stays the review artifact.

## Quality tiers

`library.json` entries carry `quality_level`: `proxy` (blockout/layout),
`standard` (preview/animatic), `hero` (final frame). A 4K texture can be hero;
a 2K model is usually standard. A higher tier is not a gate — it is a budget
decision recorded per asset.
