# EduGenie: Google Gemini Powered Learning Assistant 🧠✨

EduGenie is a lightweight AI learning assistant built with **FastAPI**, a simple **HTML + CSS + JavaScript** frontend and **Google Gemini**. Students can:

| Feature | What it does | Endpoint |
|---|---|---|
| ❓ Q&A | Ask any question and get a short, clear answer | `GET /qa?question=...` |
| 💡 Explain | Get a simple explanation of a concept (local **LaMini-Flan-T5-783M** or Gemini) | `POST /explain` `{"topic": "..."}` |
| 📝 Quiz | Generate interactive multiple-choice questions (4 options, answer checking, score) from a topic or passage | `POST /quiz` `{"text": "...", "num_questions": 3}` |
| 📄 Summarize | Turn long passages into a short revision summary | `POST /summarize` `{"text": "..."}` |
| 🗺️ Learning path | Beginner → advanced plan with timelines, resources and projects | `GET /learn/recommendations?topic=...&level=beginner` |

Also: `GET /health` (configuration status) and interactive API docs at `/docs`.

## Project structure

```
EduGenie-AI/
├── EduGenie/                   # ← the application
│   ├── main.py                 # FastAPI app + all API routes
│   ├── gemini_client.py        # Shared Gemini client (google-genai SDK), .env loading, errors
│   ├── explanation_module.py   # Concept explanation (LaMini-Flan-T5 local model, Gemini fallback)
│   ├── qna.py                  # Question answering
│   ├── quiz_module.py          # Quiz generation + JSON cleaning/validation
│   ├── summary_module.py       # Summarization
│   ├── learning_path.py        # Learning recommendations
│   ├── templates/index.html    # Frontend page (Jinja2)
│   ├── static/style.css        # Responsive styling (light + dark mode)
│   ├── static/script.js        # Frontend logic (API calls, quiz, Markdown rendering)
│   ├── tests/                  # pytest test-suite (Gemini is mocked) + optional live tests
│   ├── requirements.txt        # Core dependencies
│   ├── requirements-local.txt  # OPTIONAL local model dependencies (transformers, torch)
│   ├── .env.example            # Configuration template → copy to .env
│   └── pytest.ini
├── .vscode/                    # VS Code run/debug/test configuration
├── Project Documents/          # All phase-wise project documents (DOCX + PDF), phases 1–8
└── README.md
```

### Notes on the design vs. the original document
- The document used `google-generativeai` with `gemini-1.5-pro`. That SDK is deprecated and Gemini 1.5 models are retired, so EduGenie uses the current **`google-genai`** SDK. The model is set in `.env` (`GEMINI_MODEL`, default `gemini-flash-latest`, which always points to Google's newest Flash model).
- The local **LaMini-Flan-T5-783M** model for explanations is kept but made **optional** because it needs a ~3 GB download (PyTorch + weights). Without it, explanations use Gemini automatically.
- The API key is read from a `.env` file. It is never hard-coded (the document's screenshot had a key in the source code, which is unsafe).

---

## 1. Prerequisites

1. **Python 3.10 or newer**: <https://www.python.org/downloads/>. On Windows, tick **"Add Python to PATH"** in the installer.
   Check it with `python --version` (Windows) or `python3 --version` (macOS/Linux).
2. **VS Code**: <https://code.visualstudio.com/>, plus the **Python** extension (VS Code offers to install it when you open the folder).
3. **A Gemini API key** (free): open <https://aistudio.google.com/app/apikey>, sign in with Google, click **Create API key** and copy it.

## 2. Setup in VS Code

1. **Open the project**: *File → Open Folder…* → select the `EduGenie-AI` folder. Click **Install** if VS Code suggests the recommended extensions.
2. **Open a terminal**: *Terminal → New Terminal*.
3. **Create and activate a virtual environment** (in the `EduGenie-AI` folder):

   **Windows (PowerShell)**
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
   > If PowerShell blocks the script, run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then try again.

   **macOS / Linux**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
   Your prompt now starts with `(.venv)`. When VS Code asks *"We noticed a new environment… select it for the workspace?"* click **Yes**, or pick it via *Ctrl/Cmd+Shift+P → Python: Select Interpreter → .venv*.

4. **Install dependencies**
   ```bash
   pip install -r EduGenie/requirements.txt
   ```
   *Optional (local explanation model, ~3 GB):* `pip install -r EduGenie/requirements-local.txt`

5. **Add your API key**: copy the example config and edit it:

   Windows: `copy EduGenie\.env.example EduGenie\.env`  macOS/Linux: `cp EduGenie/.env.example EduGenie/.env`

   Open `EduGenie/.env` and replace `your_gemini_api_key_here` with your key:
   ```
   GEMINI_API_KEY=AIza...your key...
   ```

## 3. Run the application

**Option A: terminal**
```bash
cd EduGenie
uvicorn main:app --reload
```
**Option B: VS Code debugger**: open the *Run and Debug* panel (Ctrl/Cmd+Shift+D), choose **"EduGenie: Run server (uvicorn)"** and press **F5**.

Then open **<http://127.0.0.1:8000>** in your browser. The badge at the top should say **"Connected · gemini-flash-latest"**. If it says the key is missing, check `EduGenie/.env` and restart the server.

Interactive API documentation: **<http://127.0.0.1:8000/docs>**. Stop the server with **Ctrl+C**.

## 4. Test the application

### Automated tests (no API key or internet needed; Gemini is mocked)
```bash
cd EduGenie
pytest -v
```
Or use the VS Code **Testing** panel (beaker icon), or the **"EduGenie: Run tests (pytest)"** debug configuration.

### Live tests against the real Gemini API (uses your key)
```bash
cd EduGenie
# macOS / Linux
RUN_LIVE_TESTS=1 pytest -m live -v
# Windows PowerShell
$env:RUN_LIVE_TESTS="1"; pytest -m live -v
```

### Performance / load test (server must be running)
```bash
cd EduGenie
python tests/load_test.py --users 10 --duration 15
```
This sends concurrent requests to every endpoint and reports average/p95/max response time, requests per second and error rate. With a real key the AI endpoints use your Gemini quota, so keep the user count small on a free key.

### Manual functional testing (scenarios from the project document)
| Task in the dropdown | Input | Expected |
|---|---|---|
| Ask a Question | `Which is the largest ocean?` | Answer mentioning the Pacific Ocean |
| Explain a Concept | `Photosynthesis` | Simple explanation (badge shows Gemini or LaMini-Flan-T5) |
| Generate a Quiz | `The Pythagoras Theorem` | 3 MCQs, click an option → green/red feedback and a score |
| Summarize a Passage | Paste a long paragraph | Overview + key bullet points |
| Recommend a Learning Path | `SQL`, level *Beginner* | Beginner → Advanced plan with timelines and resources |

### Testing the API directly (server running)
```bash
curl "http://127.0.0.1:8000/qa?question=Which%20is%20the%20largest%20ocean%3F"
curl -X POST http://127.0.0.1:8000/explain   -H "Content-Type: application/json" -d "{\"topic\": \"Photosynthesis\"}"
curl -X POST http://127.0.0.1:8000/quiz      -H "Content-Type: application/json" -d "{\"text\": \"The Pythagoras Theorem\"}"
curl -X POST http://127.0.0.1:8000/summarize -H "Content-Type: application/json" -d "{\"text\": \"Paste a long paragraph here...\"}"
curl "http://127.0.0.1:8000/learn/recommendations?topic=SQL&level=beginner"
```
(Windows PowerShell: use `curl.exe` instead of `curl`, or just use the `/docs` page → *Try it out*.)

## Configuration (`EduGenie/.env`)

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | none | Your Google AI Studio API key (required) |
| `GEMINI_MODEL` | `gemini-flash-latest` | Any Gemini model you can access, e.g. `gemini-3.5-flash` |
| `GEMINI_FALLBACK_MODELS` | `gemini-flash-latest,gemini-flash-lite-latest` | Backup models tried when the main model is overloaded (`none` disables) |
| `GEMINI_MAX_RETRIES` | `2` | Automatic retries per model for 503 / 429 / 5xx errors (exponential backoff) |
| `EXPLAIN_BACKEND` | `auto` | `auto` (local model if installed, else Gemini), `local`, or `gemini` |
| `PRELOAD_LOCAL_MODEL` | `false` | Load the local model at startup instead of on the first request |
| `LOG_LEVEL` | `INFO` | Server log level |

## Troubleshooting

| Problem | Fix |
|---|---|
| `'uvicorn' is not recognized` / `command not found` | The virtual environment isn't active: re-run the *activate* command from step 3. |
| Badge says *Gemini API key missing* / HTTP 503 | Create `EduGenie/.env` with `GEMINI_API_KEY=...` and restart the server. |
| *API key not valid* | Re-copy the key from AI Studio; make sure there are no quotes or spaces. |
| *model … is not found* / 404 | Set `GEMINI_MODEL` to a model listed in AI Studio (e.g. `gemini-flash-latest`). |
| *This model is currently experiencing high demand* (503) | Google's servers are temporarily overloaded. EduGenie already retries automatically and switches to the backup models in `GEMINI_FALLBACK_MODELS`; if you still see the message, every model was busy. Wait a minute and click **Try again**, or set `GEMINI_MODEL` to a less busy model (e.g. `gemini-flash-lite-latest`). |
| *Quota exceeded* / 429 | Free-tier rate limit: EduGenie retries and falls back automatically; if it persists, wait a minute and try again. |
| `Address already in use` | Another server is running on port 8000: stop it or use `uvicorn main:app --reload --port 8001`. |
| `ModuleNotFoundError: main` | Run uvicorn from inside the `EduGenie` folder (`cd EduGenie`). |
| First *Explain* request is very slow | With the local model installed, the first request downloads ~3 GB. Set `EXPLAIN_BACKEND=gemini` to skip it. |

## Project documents
`Project Documents/` contains the filled-in phase-wise templates (phases 1–8) for **EduGenie: Google Gemini Powered Learning Assistant**, prepared by **Arumparithi B** (single-member team). Each document is provided as an editable **.docx** and a **.pdf**. The **Date** and **Team ID** fields are intentionally left blank / `xxxxxx` until they are assigned. Update them in the .docx files and re-export to PDF (*File → Save As / Export → PDF*). The project documentation also has marked boxes where screenshots of live AI results go once you run the app with your API key.

## Future scope
Voice interaction, multilingual support, a mobile app, progress dashboards, gamification (badges/streaks), LMS integration (Moodle / Google Classroom), and image/PDF input.
