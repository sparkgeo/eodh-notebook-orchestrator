from fastapi import FastAPI
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
async def run_notebook(id: str, cog_url: str, bbox: str = None):
    output_id = str(uuid.uuid4())
    output_path = f"notebooks/output-{output_id}.ipynb"
    os.makedirs("notebooks", exist_ok=True)

    parameters = {"cog_url": cog_url}
    if bbox:
        # Parse bbox string into a list of floats
        bbox_values = [float(x) for x in bbox.split(",")]
        parameters["bbox"] = bbox_values

    # Get notebook URL from config
    notebook_url = get_notebook_url_by_id(id)

    pm.execute_notebook(
        notebook_url,  # This can be a URL!
        output_path,
        parameters=parameters,
        prepare_only=True,
    )

    # Redirect to rendered notebook or download link
    return RedirectResponse(url=f"/view-notebook/{output_id}")


@app.get("/view-notebook/{notebook_id}")
async def view_notebook(notebook_id: str):
    return RedirectResponse(
        url=f"http://localhost:8889/lab/tree/output-{notebook_id}.ipynb"
    )
