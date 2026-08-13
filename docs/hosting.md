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
and optionally double-click `Check-SolidWorks-Setup.cmd` first. That preflight
checks the package, 64-bit PowerShell, SolidWorks registration and API files,
compiles the replay engine, and validates the replay-plan contract without
creating a part. The repository's compile-only release gate also executes the
same C# geometry comparator directly: an exact oracle must pass and an
out-of-tolerance volume must fail before native COM execution is trusted. It
also executes the production C# mutation preflight with valid pattern controls
and a deliberately collapsed linear pattern. Then run
`Build-SolidWorks-Part.cmd`; package v10 stages the native part, closes and
reopens it, verifies the saved history, exact parameter/helper identities,
localized datum/template resolution, and body/volume/area/bounds/center against
the embedded CadQuery geometry oracle, and only then writes the final part plus
a JSON verification report. The same fail-closed oracle is required by CLI,
smoke-suite, release-matrix, and capability-audit native execution paths.

## Public-release gate

Before linking the application from a LinkedIn post:

1. Download a fresh SolidWorks package from the deployed public URL.
2. Run its launcher on Windows with the supported SolidWorks version.
3. Confirm the resulting `SLDPRT` opens, rebuilds, and exposes editable named
   sketches, dimensions, patterns, and ordered features.
4. Confirm the package-v10 result reports `reopened: true`, exact verified
   parameter/helper identities, healthy features/sketches, matching geometry,
   and resolved persistent face references.
5. Run `prompt2cad-solidworks-smoke --execute --verify-editability` and require
   every native parity fixture plus the reported replay-family and edit-control
   coverage contracts to pass. This includes actual pattern count, angle, and
   two-direction spacing mutations—not only creation of patterned geometry.
6. Confirm both download buttons and the package instructions work for a new
   user without access to the repository.

The messaging requirements for that later post are recorded in
[LinkedIn launch notes](linkedin_launch_notes.md). They are release constraints,
not a prepared post draft.

Run the complete installed-application portion as one non-destructive command:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\check_solidworks_release.ps1 -Visible
```

The script creates a new timestamped evidence directory, refuses to overwrite
an earlier run, and executes the portable-package checks, all ten native
smoke/edit cases, and all seven golden native/edit cases. The ten-case report
must also cover every supported operation, source profile, support, native
pattern, feature kind, end condition, mutation mechanism, and parameter unit.
It makes no API calls.

For the final public-release gate, download a fresh package from the deployed
site and pass that exact ZIP to the same command:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\check_solidworks_release.ps1 `
  -DownloadedPackagePath "C:\Users\you\Downloads\part-v10-solidworks.zip" `
  -Visible
```

The extra gate safely extracts the ZIP, verifies every payload hash, rebuilds
the editable document, replay plan, and editability report from the embedded
source model, creates the SLDPRT, and checks exact feature/parameter/helper
identities, persistent references, and geometry equivalence. It then selects a
safe native-bound parameter, proves the corresponding edit in CadQuery,
embeds the edited geometry in a version-2 mutation document, applies it to the
downloaded SLDPRT, and saves and reopens a second SLDPRT. The runner refuses to
publish a mismatched edit. The evidence folder retains both native
parts, the mutation, machine-readable verification reports, and a complete
terminal transcript.

### Most recent verification

The public-release gate was exercised on August 10, 2026. The deployed site
generated and refined a valid multi-feature model, both public download paths
returned non-empty artifacts, and a package downloaded from the public URL
created a native SolidWorks part with editable features and dimensions. That
result predates package v10. The August 13 v10 regression now collects 647 Python
test cases with all 14 installed-API compile/setup cases passing, all six frontend
behavior suites, a production frontend build, the 7/7 golden release matrix,
and the established 292-case STEP/native-plan capability baseline. A fresh package
downloaded from the deployed site must still pass the installed-SolidWorks
build and mutation gate above before publishing. The hosted service, external
API, and installed SolidWorks version remain live dependencies.
