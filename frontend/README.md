# Frontend

React/Vite interface for Prompt2ParametricCAD.

```powershell
pnpm install
pnpm dev
```

Development requests under `/api` are proxied to
`http://127.0.0.1:8000`. Production builds use the same origin as FastAPI unless
`VITE_API_BASE_URL` is set.

```powershell
pnpm build
pnpm qa
```

The complete setup and launch workflow is in
[`../docs/setup.md`](../docs/setup.md).
