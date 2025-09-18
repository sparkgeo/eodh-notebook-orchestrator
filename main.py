import os
import time
import logging
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, HttpUrl, validator
from create_qlr.create_qlr import create_qlr
from run_notebook.run_notebook import execute_notebook, get_view_notebook_url

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Jupyter Notebook API",
    description="API for executing notebooks and generating QLR files",
    version="0.1.0",
)

# Environment-based CORS configuration
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with timing information"""
    # Check if request logging is enabled
    if not os.getenv("LOG_REQUESTS", "true").lower() == "true":
        return await call_next(request)

    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    # Log request details
    logger.info(
        f"Request started: {request.method} {request.url.path} "
        f"from {client_ip} (User-Agent: {user_agent})"
    )

    # Log query parameters if present
    if request.query_params:
        logger.debug(f"Query params: {dict(request.query_params)}")

    # Log request body for POST/PUT requests if enabled
    if os.getenv("LOG_REQUEST_BODY", "false").lower() == "true" and request.method in [
        "POST",
        "PUT",
        "PATCH",
    ]:
        try:
            body = await request.body()
            if body:
                logger.debug(
                    f"Request body: {body.decode('utf-8')[:500]}..."
                )  # Limit to 500 chars
        except Exception as e:
            logger.warning(f"Could not read request body: {e}")

    # Process the request
    try:
        response = await call_next(request)
    except Exception as e:
        # Log any unhandled exceptions
        process_time = time.time() - start_time
        logger.error(
            f"Request failed: {request.method} {request.url.path} "
            f"-> Exception: {str(e)} in {process_time:.3f}s"
        )
        raise

    # Calculate processing time
    process_time = time.time() - start_time

    # Log response details
    status_emoji = (
        "✅"
        if 200 <= response.status_code < 300
        else "❌"
        if response.status_code >= 400
        else "⚠️"
    )
    logger.info(
        f"Request completed: {request.method} {request.url.path} "
        f"-> {response.status_code} {status_emoji} in {process_time:.3f}s"
    )

    # Add timing header to response
    response.headers["X-Process-Time"] = str(round(process_time, 3))

    return response


class QLRRequest(BaseModel):
    url: HttpUrl
    collection: str

    @validator("collection")
    def validate_collection(cls, v):
        if not v or not v.strip():
            raise ValueError("Collection cannot be empty")
        return v.strip()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/run/notebook/{notebook_id}")
async def run_notebook(notebook_id: str, request: Request):
    """Execute a notebook with the given ID and request parameters"""
    try:
        # Validate notebook ID
        if not notebook_id or not notebook_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Notebook ID cannot be empty",
            )

        # Sanitize notebook ID (basic security check)
        if not notebook_id.replace("-", "").replace("_", "").isalnum():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid notebook ID format",
            )

        output_id = execute_notebook(notebook_id.strip(), request)
        return RedirectResponse(url=f"/view-notebook/{notebook_id}/{output_id}")

    except ValueError as e:
        logger.error(f"Notebook execution failed: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during notebook execution: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@app.get("/view-notebook/{notebook_id}/{output_id}")
async def view_notebook(notebook_id: str, output_id: str):
    """Generate URL for viewing a notebook"""
    try:
        # Validate inputs
        if not notebook_id or not output_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Notebook ID and output ID are required",
            )

        # Sanitize inputs
        if not notebook_id.replace("-", "").replace("_", "").isalnum():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid notebook ID format",
            )

        if not output_id.replace("-", "").isalnum():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid output ID format",
            )

        view_url = get_view_notebook_url(notebook_id, output_id)
        return RedirectResponse(url=view_url)

    except Exception as e:
        logger.error(f"Error generating view URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating view URL",
        )


@app.get("/qlr")
async def get_qlr(url: str, collection: str):
    try:
        qlr_xml = create_qlr(str(url), collection)
        logger.info(f"QLR created successfully for {url} with collection {collection}")
        output_filename = Path(url).name + ".qlr"
        return Response(
            content=qlr_xml,
            media_type="application/xml",
            headers={
                "Content-Disposition": f'attachment; filename="{output_filename}"'
            },
        )
    except ValueError as e:
        logger.error(f"QLR generation failed: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during QLR generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
