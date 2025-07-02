# Jupyter Test: FastAPI + JupyterLab NDVI Notebook Runner

This project provides a FastAPI web service that executes a parameterized Jupyter notebook (for NDVI calculation) using [Papermill](https://papermill.readthedocs.io/) and allows you to view the results in JupyterLab.

## Features

- **Run a notebook remotely:** Trigger execution of a notebook with a custom GeoTIFF URL and optional bounding box (bbox).
- **View results in JupyterLab:** Redirects to a JupyterLab instance to view the output notebook.

## Requirements

- Python 3.13+
- [JupyterLab](https://jupyterlab.readthedocs.io/)
- [Uvicorn](https://www.uvicorn.org/) (for running FastAPI)
- All dependencies in `pyproject.toml` (install with your preferred tool, e.g. `pip`, `uv`, or `poetry`)

## Installation

1. **Clone the repository** and navigate to the project directory.

2. **Install dependencies** (using pip as an example):

   ```bash
   pip install fastapi jupyterlab papermill rioxarray matplotlib uvicorn
   ```

   Or, to use the exact versions in `pyproject.toml`:

   ```bash
   pip install -r requirements.txt
   # or use uv/poetry as appropriate
   ```

## Usage

### 1. Start JupyterLab

You must have a JupyterLab server running so the FastAPI app can redirect you to view the output notebooks.

```bash
jupyter lab --notebook-dir=notebooks --port=8889
```

- The `--notebook-dir=notebooks` flag ensures output notebooks are saved and accessible in the correct folder.
- The `--port=8889` flag matches the redirect URL in `main.py`.

### 2. Start the FastAPI App

Run the FastAPI app using Uvicorn:

```bash
uvicorn main:app --reload
```

- By default, this will start the API at `http://127.0.0.1:8000`.

### 3. Run a Notebook

Open your browser and visit:

```
http://127.0.0.1:8000/run-notebook?cog_url=YOUR_COG_URL&bbox=min_lon,min_lat,max_lon,max_lat
```

- Replace `YOUR_COG_URL` with the URL to your GeoTIFF file.
- The `bbox` parameter is optional. If provided, it should be four comma-separated values: `min_lon,min_lat,max_lon,max_lat` (in WGS84/EPSG:4326 coordinates).
- Example:

```
http://127.0.0.1:8000/run-notebook?cog_url=https%3A%2F%2Fdap.ceda.ac.uk%2Fneodc%2Fsentinel_ard%2Fdata%2Fsentinel_2%2F2025%2F06%2F20%2FS2B_20250620_latn537lonw0037_T30UVE_ORB080_20250620132615_utm30n_osgb_vmsk_sharp_rad_srefdem_stdsref.tif&bbox=-4.531313295277459,53.151777988193025,-4.5213132952774595,53.16177798819302
```

- This will execute the `templates/ndvi_calculation.ipynb` notebook with the provided parameters.
- After execution, you will be redirected to JupyterLab to view the output notebook.

## File Structure

- `main.py` — FastAPI app for running and viewing notebooks
- `templates/ndvi_calculation.ipynb` — Parameterized notebook template
- `notebooks/` — Output notebooks are saved here
- `pyproject.toml` — Project dependencies

## Notes

- Make sure the JupyterLab server is running and accessible at `http://localhost:8889/lab/tree/notebooks/`.
- The FastAPI app does not serve the notebook files directly; it only redirects to JupyterLab.
- The notebook will use the provided `bbox` if given, otherwise it will use a default bounding box.

## Troubleshooting

- If you get a 404 when redirected, ensure JupyterLab is running and the output notebook exists in the `notebooks/` directory.
- If you see errors about missing dependencies, double-check your Python environment and install all required packages.

---
