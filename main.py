from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import papermill as pm
import uuid
import os

app = FastAPI()


@app.get("/run-notebook")
async def run_notebook(
    cog_url: str, bbox: str = None, notebook: str = "ndvi_calculation.ipynb"
):
    output_id = str(uuid.uuid4())
    output_path = f"notebooks/output-{output_id}.ipynb"
    os.makedirs("notebooks", exist_ok=True)

    parameters = {"cog_url": cog_url}
    if bbox:
        # Parse bbox string into a list of floats
        bbox_values = [float(x) for x in bbox.split(",")]
        parameters["bbox"] = bbox_values

    pm.execute_notebook(
        f"templates/{notebook}",
        output_path,
        parameters=parameters,
        prepare_only=True,
    )

    # Redirect to rendered notebook or download link
    return RedirectResponse(url=f"/view-notebook/{output_id}")


@app.get("/view-notebook/{notebook_id}")
async def view_notebook(notebook_id: str):
    return RedirectResponse(
        url=f"http://localhost:8889/lab/tree/notebooks/output-{notebook_id}.ipynb"
    )
