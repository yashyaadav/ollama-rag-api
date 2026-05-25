# How the README assets are produced

The README references two static assets:

- `docs/demo.gif` — a ~10s terminal cast of `make ingest` + `curl /ask`
- `docs/swagger.png` — a screenshot of the Swagger UI at `/apidocs`

Both need a live API + Ollama to produce, which is why they're recorded
by hand rather than generated in CI. This file documents the exact
reproducible recipe so re-recording on a model/feature change is easy.

## Prereqs (one-time)

```bash
brew install vhs            # terminal cast → gif, scriptable
# OR:  brew install asciinema && cargo install --git https://github.com/asciinema/agg
```

## Capture `docs/demo.gif`

1. Make sure the API and Ollama aren't running on `:5000` / `:11434`.
2. Place a small document under `source_documents/` (the repo ships
   with a `test.pdf` for this).
3. From the repo root, run:

   ```bash
   vhs docs/demo.tape
   ```

   This produces `docs/demo.gif`. The tape file below drives:
   - `make ingest`
   - `make api &` (background) + brief wait
   - `examples/curl.sh "What is this document about?"`

Create `docs/demo.tape` if it doesn't exist:

```tape
Output docs/demo.gif
Set FontSize 14
Set Width 1100
Set Height 600
Set Theme "Dracula"
Type "make ingest"
Enter
Sleep 2s
Type "make api &"
Enter
Sleep 6s
Type "./examples/curl.sh 'What is this document about?'"
Enter
Sleep 8s
```

## Capture `docs/swagger.png`

1. `make run` (or just `make api`).
2. Open http://localhost:5000/apidocs in a browser.
3. Expand the **POST /ask** endpoint so the request/response schema is
   visible.
4. Take a screenshot of the page (macOS: `Cmd+Shift+4`, drag a tight
   rectangle around the Swagger panel).
5. Save as `docs/swagger.png`.

## Re-recording cadence

Re-record when any of these change:

- The `/ask` or `/health` request/response shape (Swagger screenshot)
- The Makefile target names shown in the gif
- The default `MODEL` (the answer in the gif will look different)
