from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from create_qlr.create_qlr import create_qlr
from fastapi.responses import Response
from run_notebook.run_notebook import execute_notebook, get_view_notebook_url

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],  # Frontend origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/run/notebook/{id}")
async def run_notebook(id: str, request: Request):
    output_id = execute_notebook(id, request)
    return RedirectResponse(url=f"/view-notebook/{id}/{output_id}")


@app.get("/view-notebook/{notebook_id}/{output_id}")
async def view_notebook(notebook_id: str, output_id: str):
    return RedirectResponse(url=get_view_notebook_url(notebook_id, output_id))


@app.get("/qlr")
async def get_qlr(url: str, collection: str):
    try:
        qlr_xml = create_qlr(url, collection)
        return Response(
            content=qlr_xml,
            media_type="application/xml",
            headers={"Content-Disposition": 'attachment; filename="layer.qlr"'},
        )
    except Exception as e:
        return Response(str(e), status_code=400)
