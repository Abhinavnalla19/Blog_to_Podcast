# Blog to Podcast

A Python project and Streamlit UI to convert blog content into podcast-ready audio. The app orchestrates content ingestion, text processing, synthesis, and audio validation.

**Quick Summary**

- `blog_to_podcast_agent.py` — Streamlit app and main orchestration.
- `scripts/check_audio.py` — audio validation and basic checks.
- `requirements.txt` — installable dependencies for the app.
- `.env.example` — example environment configuration.
- `.gitignore` — excludes `.venv/`, `extensions/`, `logs/`, and other generated files.

**Features**

- Convert blog posts (markdown / HTML / URL) into narration-ready text.
- Generate audio using TTS or external model APIs.
- Basic post-processing (silence trimming, normalization).
- Validation utilities to check duration, format, and silence segments.

**Requirements**

- Python 3.10+ (tested on 3.12)
- Recommended: a virtual environment

Install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # PowerShell
pip install --upgrade pip
pip install -r requirements.txt
```

**Configuration**

1. Copy `.env.example` to `.env` and set values.
2. Typical environment variables:
  - `OPENAI_API_KEY` or other model keys
  - `OUTPUT_DIR` — where audio files are saved
  - `STREAMLIT_SERVER_PORT` — optional

**Run (development)**

Start the Streamlit UI (recommended):

```powershell
streamlit run "blog_to_podcast_agent.py"
```

Run scripts directly (useful for utilities):

```powershell
.\.venv\Scripts\python.exe scripts/check_audio.py
```

**Example workflow**

1. Provide a blog URL or paste content into the Streamlit UI.
2. Choose voice / TTS settings and start generation.
3. Download or inspect generated audio in the configured `OUTPUT_DIR`.
4. Run `python scripts/check_audio.py` to validate files.

**Troubleshooting**

- Streamlit warnings when running `python blog_to_podcast_agent.py` are normal — use `streamlit run` to open the app in the browser.
- If audio generation fails, check that API keys are set and the `requirements.txt` packages are installed.
- Large files and editor extensions were present in the working copy; `.gitignore` was added to avoid tracking them moving forward. Large files that already exist in the remote history are not removed by `.gitignore`.

**Repository / Git notes**

- `.gitignore` added to avoid tracking virtualenvs, `extensions/`, and logs.
- Remote already contains some large binaries; to remove them from history you can use `git filter-repo` or BFG and then force-push (I can help with that if you want).

**Development tips**

- Add a small helper script (`run.ps1` or `Makefile`) to set up the venv and run Streamlit quickly.
- Add tests for the audio validation pipeline under `tests/`.

**Contributing**

- Fork, branch, add tests, and open a PR.

**License**

- If you want a license, add a `LICENSE` file (MIT, Apache-2.0, etc.).

---

Would you like me to commit and push this update to the remote? If yes, I will commit and push now.
