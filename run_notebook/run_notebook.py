import papermill as pm
import uuid
import os
import requests
from typing import Dict, Any
from fastapi import Request
import jupyter_client

CONFIG_URL = "https://raw.githubusercontent.com/geodowd/notebook_config/refs/heads/main/config.json"


def get_notebook_config(notebook_id: str) -> Dict[str, Any]:
    """Get notebook configuration by ID."""
    resp = requests.get(CONFIG_URL)
    config = resp.json()
    # Only look at notebook type items and check if id exists
    notebook = next(
        (
            nb
            for nb in config
            if nb.get("type") == "notebook" and nb.get("id") == notebook_id
        ),
        None,
    )
    if not notebook:
        raise ValueError(f"Notebook id '{notebook_id}' not found in config.")
    return notebook


def parse_parameters(request: Request, input_spec: Dict[str, str]) -> Dict[str, Any]:
    """Parse and validate parameters from request query params based on input specification."""
    query_params = dict(request.query_params)
    parameters = {}

    for param, param_type in input_spec.items():
        if param not in query_params:
            continue
        value = query_params[param]

        if param_type == "bbox":
            parameters[param] = [float(x) for x in value.split(",")]
        elif param_type == "urlList":
            parameters[param] = value.split(",")
        else:
            parameters[param] = value

    return parameters


def get_default_kernel_name() -> str:
    """Get the default kernel name from available kernels."""
    try:
        kernels = jupyter_client.kernelspec.KernelSpecManager()
        kernel_specs = kernels.get_all_specs()
        # Try to find python3 first, then any python kernel, then the first available
        if "python3" in kernel_specs:
            return "python3"
        elif "python" in kernel_specs:
            return "python"
        elif kernel_specs:
            return list(kernel_specs.keys())[0]
        else:
            return "python3"  # fallback
    except Exception:
        return "python3"  # fallback


def execute_notebook(notebook_id: str, request: Request) -> str:
    """
    Execute a notebook with the given ID and request parameters.

    Args:
        notebook_id: The ID of the notebook to execute
        request: FastAPI request object containing query parameters

    Returns:
        str: The output notebook ID for viewing
    """
    output_id = str(uuid.uuid4())
    output_path = f"notebooks/{notebook_id}-{output_id}.ipynb"
    os.makedirs("notebooks", exist_ok=True)

    # Get notebook config and inputSpec
    notebook = get_notebook_config(notebook_id)
    input_spec = notebook.get("inputSpec", {})

    # Extract and parse parameters dynamically
    parameters = parse_parameters(request, input_spec)

    # Get default kernel name
    kernel_name = get_default_kernel_name()

    # Run notebook
    pm.execute_notebook(
        notebook["file"],
        output_path,
        parameters=parameters,
        prepare_only=True,
        kernel_name=kernel_name,  # Use detected kernel
    )

    return output_id


def get_view_notebook_url(notebook_id: str, output_id: str) -> str:
    """Generate the URL for viewing a notebook."""
    return f"http://localhost:8889/lab/tree/{notebook_id}-{output_id}.ipynb"
