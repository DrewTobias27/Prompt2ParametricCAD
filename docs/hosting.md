# Hosting Prompt2ParametricCAD

The public application is deployed as one Docker web service. The container
builds the React frontend, installs the FastAPI/CadQuery backend, and serves
both from one origin.

## Render settings

The repository includes `render.yaml`. Creating a Render Blueprint from the
repository applies the service, health-check, and runtime settings.

The Blueprint requests Render's paid `standard` instance because its 2 GB RAM
and dedicated CPU are a safer baseline for CadQuery/OpenCascade than the free
512 MB service. Render shows the cost before the Blueprint is created. A free
instance can be used for an initial deployment experiment by changing `plan` to
`free`, but it can sleep when idle and is not the recommended portfolio link.

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
4. Generate one known-good prompt and download its STEP file.
5. Confirm the API key is present only in Render's secret settings.

The hosted application exports STEP and editable model data. Native SolidWorks
replay remains a local Windows feature because it requires an installed and
licensed SolidWorks application.
