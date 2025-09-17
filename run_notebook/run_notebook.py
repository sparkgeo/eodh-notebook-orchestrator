import papermill as pm
import uuid
import os
import requests
import time
import logging
from typing import Dict, Any
from fastapi import Request, HTTPException
import jupyter_client
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_URL = "https://raw.githubusercontent.com/geodowd/notebook_config/refs/heads/main/config.json"
CONFIG_CACHE_DURATION = 300  # 5 minutes
_config_cache = {"data": None, "timestamp": 0}


def get_notebook_config(notebook_id: str) -> Dict[str, Any]:
    """Get notebook configuration by ID with caching"""
    current_time = time.time()

    # Check if cache is valid
    if (
        _config_cache["data"] is not None
        and current_time - _config_cache["timestamp"] < CONFIG_CACHE_DURATION
    ):
        config = _config_cache["data"]
    else:
        try:
            resp = requests.get(CONFIG_URL, timeout=10)
            resp.raise_for_status()
            config = resp.json()
            _config_cache["data"] = config
            _config_cache["timestamp"] = current_time
            logger.info("Notebook configuration loaded and cached")
        except requests.RequestException as e:
            logger.error(f"Failed to fetch config: {e}")
            raise HTTPException(
                status_code=500, detail="Failed to fetch notebook configuration"
            )

    # Validate notebook ID
    if not notebook_id or not isinstance(notebook_id, str):
        raise ValueError("Notebook ID must be a non-empty string")

    # Find notebook
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
    """Parse and validate parameters from request query params with proper error handling."""
    query_params = dict(request.query_params)
    parameters = {}

    for param, param_type in input_spec.items():
        if param not in query_params:
            continue

        value = query_params[param]

        try:
            if param_type == "bbox":
                # Validate bbox format: minx,miny,maxx,maxy
                coords = [float(x) for x in value.split(",")]
                if len(coords) != 4:
                    logger.warning(f"Invalid bbox format for {param}: {value}")
                    continue
                parameters[param] = coords
            elif param_type == "urlList":
                # Validate URL list
                urls = [url.strip() for url in value.split(",") if url.strip()]
                if not urls:
                    logger.warning(f"Empty URL list for {param}")
                    continue
                parameters[param] = urls
            else:
                # Basic string validation
                if not value.strip():
                    logger.warning(f"Empty value for {param}")
                    continue
                parameters[param] = value.strip()
        except ValueError as e:
            logger.warning(f"Invalid parameter {param}: {e}")
            continue

    return parameters


def get_default_kernel_name() -> str:
    """Get the default kernel name from available kernels."""
    try:
        kernels = jupyter_client.kernelspec.KernelSpecManager()
        kernel_specs = kernels.get_all_specs()

        # Priority order for kernel selection
        preferred_kernels = [
            "python3 (ipykernel)",
            "python3",
            "python",
            "jupyter-python3",
        ]

        for kernel_name in preferred_kernels:
            if kernel_name in kernel_specs:
                logger.info(f"Using kernel: {kernel_name}")
                return kernel_name

        # Fallback to first available kernel
        if kernel_specs:
            kernel_name = list(kernel_specs.keys())[0]
            logger.info(f"Using fallback kernel: {kernel_name}")
            return kernel_name
        else:
            logger.warning("No kernels available, using default python3")
            return "python3"
    except Exception as e:
        logger.warning(f"Failed to detect kernel: {e}, using default python3")
        return "python3"


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
    notebooks_dir = Path("notebooks")
    notebooks_dir.mkdir(exist_ok=True)
    output_path = notebooks_dir / f"{notebook_id}-{output_id}.ipynb"

    try:
        # Get notebook config and inputSpec
        notebook = get_notebook_config(notebook_id)
        input_spec = notebook.get("inputSpec", {})

        # Extract and parse parameters
        parameters = parse_parameters(request, input_spec)

        # Get kernel name
        kernel_name = get_default_kernel_name()

        # Execute notebook
        pm.execute_notebook(
            notebook["file"],
            str(output_path),
            parameters=parameters,
            prepare_only=True,
            kernel_name=kernel_name,
        )

        logger.info(
            f"Notebook {notebook_id} executed successfully with output {output_id}"
        )
        return output_id

    except Exception as e:
        # Clean up failed output file
        if output_path.exists():
            output_path.unlink()
            logger.info(f"Cleaned up failed output file: {output_path}")
        logger.error(f"Notebook execution failed: {e}")
        raise


def get_view_notebook_url(notebook_id: str, output_id: str) -> str:
    """Generate the URL for viewing a notebook with configurable base URL."""
    # This should be configurable via environment variables
    jupyter_base_url = os.getenv("JUPYTER_BASE_URL", "http://localhost:8889")
    return f"{jupyter_base_url}/lab/tree/{notebook_id}-{output_id}.ipynb"
