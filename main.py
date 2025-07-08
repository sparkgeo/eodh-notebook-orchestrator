from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
import papermill as pm
import uuid
import os
import requests

app = FastAPI()

CONFIG_URL = "https://raw.githubusercontent.com/geodowd/notebook_config/refs/heads/main/config.json"


def get_notebook_url_by_id(notebook_id: str) -> str:
    resp = requests.get(CONFIG_URL)
    config = resp.json()
    for nb in config["notebooks"]:
        if nb["id"] == notebook_id:
            return nb["file"]
    raise ValueError(f"Notebook id '{notebook_id}' not found in config.")


@app.get("/run/notebook/{id}")
async def run_notebook(id: str, request: Request):
    output_id = str(uuid.uuid4())
    output_path = f"notebooks/output-{output_id}.ipynb"
    os.makedirs("notebooks", exist_ok=True)

    # Get notebook config and inputSpec
    resp = requests.get(CONFIG_URL)
    config = resp.json()
    notebook = next((nb for nb in config["notebooks"] if nb["id"] == id), None)
    if not notebook:
        raise ValueError(f"Notebook id '{id}' not found in config.")
    input_spec = notebook.get("inputSpec", {})

    # Extract and parse parameters dynamically
    query_params = dict(request.query_params)
    parameters = {}
    for param, param_type in input_spec.items():
        if param not in query_params:
            continue  # Optionally, raise error if required
        value = query_params[param]
        if param_type == "bbox":
            parameters[param] = [float(x) for x in value.split(",")]
        elif param_type == "urlList":
            parameters[param] = value.split(",")
        else:
            parameters[param] = value

    # Run notebook
    pm.execute_notebook(
        notebook["file"],
        output_path,
        parameters=parameters,
        prepare_only=True,
    )

    return RedirectResponse(url=f"/view-notebook/{output_id}")


@app.get("/view-notebook/{notebook_id}")
async def view_notebook(notebook_id: str):
    return RedirectResponse(
        url=f"http://localhost:8889/lab/tree/output-{notebook_id}.ipynb"
    )
