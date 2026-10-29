# Pharmind

A local pharmacology research workspace. Read papers, explore compounds, and keep a browser-based research notebook with an AI model you choose.

The interface uses Playfair Display Black, Helvetica Neue / Arial, and a restrained slate, ink, mauve, steel, and pale-blue palette. Fonts are served locally.

## Screenshots

### Research workspace

Start directly in the workspace, choose a research mode, and keep your notebooks in the sidebar.

![Pharmind research workspace](docs/screenshots/workspace.jpg)

<details>
<summary>Local model setup</summary>

Configure an installed Ollama model and its local endpoint.

![Ollama local model connection settings](docs/screenshots/local-model.jpg)

</details>

<details>
<summary>Bring your own key</summary>

Choose your provider and enter your own model ID and API key. No credentials are shown in this screenshot.

![Bring-your-own-key provider settings](docs/screenshots/byok.jpg)

</details>

## Choose how your AI runs

- **Local:** Ollama runs a downloaded model on your computer. Online literature sources are off by default. Research requests use cached embedding and reranking models and your local document index.
- **Bring your own key:** OpenAI, Anthropic, and Google Gemini are optional. Your questions, conversation context, and selected evidence are sent through your local backend to the provider you select. The provider's terms and charges apply. This mode is not offline inference.
- **Online sources:** A separate, explicit setting enables literature searches and compound lookups through public databases. Choosing a cloud AI provider does not automatically enable these searches.

Pharmind has no account, trial, subscription, or shared service key. It is intended for a trusted, single-user local installation; keep its ports bound to loopback rather than exposing them publicly.

For research and education only. Generated answers need source verification and are not medical advice.

## Start with Docker

1. Install and start Docker Desktop.
2. Copy `backend/.env.example` to `backend/.env` if it does not exist. The example defaults to Ollama and disables online sources.
3. Run `docker compose up -d --build`.
4. Prepare the document models once while connected to the internet:

   ```sh
   docker compose exec -T backend python scripts/prepare_local_models.py
   ```

5. For local inference, install Ollama on your host, start it, and download a model:

   ```sh
   ollama pull qwen2.5:3b
   ```

6. Open [connection settings](http://localhost:3000/settings). Choose your engine, enter the exact installed or provider model ID, test the connection, and save it for this browser session.
7. Open the workspace and add a PDF through **Document library** or **Add a paper**.

On Windows, `start-pharmer.bat` builds the containers, prepares the document model cache, and opens the workspace. It does not ask for a cloud key or automatically ingest online literature. Use `stop-pharmer.bat` to stop the app.

Initial dependency and model downloads require internet access. After preparation, local mode can operate offline. If a model is missing, the app reports the setup step instead of downloading it during your research request.

The Docker backend reaches host Ollama through `host.docker.internal`. The default localhost address in the UI maps to the configured `OLLAMA_BASE_URL`. Compose publishes both application ports only on `127.0.0.1`.

## Start without Docker

Use Python 3.10+ and a supported Node.js version for Next.js 16. Install the existing dependencies:

```sh
cd backend
python -m venv .venv
# Activate .venv for your shell, then:
pip install -r requirements.txt
python scripts/prepare_local_models.py
uvicorn main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open [Pharmind](http://localhost:3000) to start in the workspace. Configure your model through **Model & connection** in the sidebar.

## Where your information lives

| Information | Location |
| --- | --- |
| Conversations and notebooks | Browser local storage |
| Connection and entered API key | This tab's session storage; clear with **Forget saved connection** |
| Uploaded PDFs and extracted passages | Local backend data directory and ChromaDB |
| Embedding and reranking models | `PHARMER_MODEL_CACHE`, default `backend/.cache` when run from the backend |
| BYOK requests | Selected provider, via the local backend |

Entered keys are not written to backend files, included in chat history, or returned by the connection test. Session storage is accessible to scripts on the app's origin; it is not an encrypted credential vault. Environment variables remain available for command-line workflows. Browser requests carry their own selected settings, independently of those variables.

Connection testing checks Ollama's installed model list or the selected provider's model endpoint. It does not send a research prompt or verify answer quality.

Local mode blocks automatic external structure images and the externally hosted visual molecule editor. You can still enter SMILES and use the editor's local templates. Enabling online sources enables the external editor and structure images as well as database lookups. Clicking an external citation is a deliberate visit to that source.

## Research workflow

- **Paper learning:** Upload and index literature, then ask about methods, findings, and limitations.
- **Structure & science:** Enter a compound name or SMILES to explore structures and grounded profiles. Offline name resolution depends on locally available records; import literature or use SMILES when a compound is unavailable.
- **Molecule theory:** Ask about mechanisms, interactions, and structure–activity relationships.
- **Notebooks:** Conversations are saved in the browser and can be reopened or deleted from the sidebar.
- **References:** Inspect source passages and export profiles. Existing comparisons and citation tools remain available.

## Checks

```sh
cd frontend
npm run build
```

```sh
cd backend
python -m unittest scripts.test_connection -v
python -m compileall -q rag ingest main.py
```

Connection tests cover provider selection, session isolation across concurrent streams, key redaction, model availability checks, and online-source blocking. They use mocked providers and do not need real API keys or a running Ollama instance.

## License

MIT. Playfair Display is bundled under the SIL Open Font License in `frontend/public/fonts/OFL.txt`.
