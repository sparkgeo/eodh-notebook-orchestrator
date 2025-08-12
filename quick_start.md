# Quick Start instructions

## Setup env

```bash
source .venv/bin/activate
```

## Start JupyterLab

You must have a JupyterLab server running so the FastAPI app can redirect you to view the output notebooks.

```bash
jupyter lab --notebook-dir=notebooks --port=8889
```

- The `--notebook-dir=notebooks` flag ensures output notebooks are saved and accessible in the correct folder.
- The `--port=8889` flag matches the redirect URL in `main.py`.

## Start the FastAPI App

Run the FastAPI app using Uvicorn:

```bash
uvicorn main:app --reload
```
