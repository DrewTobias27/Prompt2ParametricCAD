# Hosting Prompt2ParametricCAD

The public application is deployed as one Docker web service. The container
builds the React frontend, installs the FastAPI/CadQuery backend, and serves
both from one origin.

## Render settings

The repository includes `render.yaml`. Creating a Render Blueprint from the
repository applies the service, health-check, and runtime settings.

The Blueprint defaults to Render's free instance so the portfolio prototype can
be hosted without adding payment information. Free services have 512 MB RAM and
sleep when idle, so the first request after a quiet period can be slow and
CadQuery/OpenCascade might exceed the available memory on complex parts. If
that happens, keep the full generator local rather than silently weakening its
geometry pipeline.

The only required secret is:

- `OPENAI_API_KEY`: a project-scoped OpenAI API key. Enter it in Render; never
  add it to this repository or expose it through a `VITE_` environment value.

Public-demo safeguards are configured with:

- `PROMPT2CAD_PUBLIC_RATE_LIMIT_REQUESTS`: AI-backed requests allowed per IP
  during one window; `0` disables the limiter for local development.
- `PROMPT2CAD_PUBLIC_RATE_LIMIT_WINDOW_SECONDS`: rate-limit window length.
- `PROMPT2CAD_STEP_MAX_AGE_SECONDS`: age after which generated STEP downloads
  are removed.
- `PROMPT2CAD_STEP_MAX_FILES`: maximum recent STEP downloads retained by one
  service instance.

The generated files are intentionally temporary. Render's normal filesystem is
ephemeral, and the application does not require a persistent disk for immediate
STEP downloads.

## Deployment check

After deployment:

1. Open `/health` and confirm `{"status":"ok"}`.
2. Open `/` and confirm the React application loads.
3. Build one manual model and download its STEP file.
4. Download its SolidWorks package and inspect `manifest.json` and the replay
   plan inside the ZIP.
5. Generate one known-good prompt and download its STEP file.
6. Confirm the API key is present only in Render's secret settings.

The hosted application exports STEP, editable model data, and a validated
SolidWorks replay package. The package is generated in memory and contains no
API credentials. Native `SLDPRT` creation remains a local Windows step because
it requires an installed and licensed SolidWorks application: extract the ZIP
and double-click `Build-SolidWorks-Part.cmd`. The package checks its payload,
discovers the installed SolidWorks API, and writes both the native part and a
JSON verification report.

## Public-release gate

Before linking the application from a LinkedIn post:

1. Download a fresh SolidWorks package from the deployed public URL.
2. Run its launcher on Windows with the supported SolidWorks version.
3. Confirm the resulting `SLDPRT` opens, rebuilds, and exposes editable named
   sketches, dimensions, patterns, and ordered features.
4. Run `prompt2cad-solidworks-smoke --execute` and require every native parity
   fixture to pass.
5. Confirm both download buttons and the package instructions work for a new
   user without access to the repository.

The messaging requirements for that later post are recorded in
[LinkedIn launch notes](linkedin_launch_notes.md). They are release constraints,
not a prepared post draft.

### Most recent verification

The public-release gate was exercised on August 10, 2026. The deployed site
generated and refined a valid multi-feature model, both public download paths
returned non-empty artifacts, and a package downloaded from the public URL
created a native SolidWorks part with editable features and dimensions. The
native parity suite passed all eight supported cases. Repeat the short human
check immediately before publishing because the hosted service and external
API remain live dependencies.
