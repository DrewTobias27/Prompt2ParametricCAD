# Demo checklist

Use this checklist before showing Prompt2CAD from a laptop while the CAD server
runs on the development computer.

## 1. Start the server on the development computer

From the repository root:

```powershell
$env:PROMPT2CAD_PYTHON = "C:\Users\Drew Tobias\Documents\Codex\2026-06-19\let\work\cadquery-env\Scripts\python.exe"
$env:PYTHONPATH = "src"
.\scripts\run_demo_server.ps1
```

If prompt generation is needed, make sure `OPENAI_API_KEY` is set in the same
terminal before starting the server.

## 2. Open the app from the laptop

On the development computer, find its local IP:

```powershell
ipconfig
```

On the laptop, open:

```text
http://YOUR-IPV4-ADDRESS:8000/
```

Both computers must be on the same network. If Windows Firewall asks, allow
Python on private networks.

## 3. Quick health checks

In the web app:

1. Select **Circular flange with bolt holes**.
2. Click **Use prompt**.
3. Click **Generate CAD**.
4. Confirm a **Download STEP file** link appears.
5. Copy JSON or download the STEP file if useful for the demo.

This runs the full prompt → API → design intent → CAD JSON → CadQuery → STEP
pipeline.

## 4. Safe demo prompts

These prompts are good first choices:

- Create an 80 mm diameter circular flange, 8 mm thick, with six 6 mm circular
  through holes evenly spaced around the center.
- Create an 80 by 50 by 20 mm rectangular block. Add a centered 10 mm circular
  through hole on the front face and a raised rectangular boss on the top face.
- Create a capsule-shaped cylinder with hemispherical ends, 20 mm diameter and
  80 mm long.
- Create a D-shaped plate with a flat back edge and rounded front, two
  rectangular side tabs, and three circular through holes along the centerline.

## 5. Recovery plan

If prompt generation fails:

- Try one of the known-good demo prompts.
- Simplify the prompt and generate again.
- Use the output JSON/error summary to explain what part of the intent failed.
- Switch to the manual builder if you need to demonstrate controlled CAD
  construction without relying on a freeform prompt.

There is also a backend-only saved demo route for emergency debugging, but it is
not part of the normal demo flow because it bypasses the live AI generation
pipeline.

If you need it during a private dry run, call `/build-demo` with a whitelisted
demo id from developer tools or a script.

If the laptop cannot connect:

- Confirm the server command used `--host 0.0.0.0`.
- Confirm both computers are on the same network.
- Try opening `http://127.0.0.1:8000/` on the development computer.
- Check Windows Firewall/private-network permission.

If the generated geometry is valid but not what was intended:

- Use the output JSON to discuss the current intent gap.
- Switch to another known-good prompt or manual builder example.
- Do not keep regenerating the same prompt repeatedly during the demo.
