import rasterio
from rasterio.warp import transform_bounds
from create_qlr.get_template import get_template_path
import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def get_cog_metadata(url: str) -> Dict[str, Any]:
    """
    Reads a COG's metadata from a given URL.
    Returns a dictionary with extent, wgs84_extent, crs info, width, height, band count, and dtype.
    """
    try:
        with rasterio.open(url) as src:
            bounds = src.bounds
            crs = src.crs
            width = src.width
            height = src.height
            count = src.count
            dtype = src.dtypes[0]

            # Transform bounds to WGS84
            wgs84_bounds = transform_bounds(crs, "EPSG:4326", *bounds)

            metadata = {
                "extent": bounds,
                "wgs84_extent": wgs84_bounds,
                "crs_wkt": crs.to_wkt() if crs else None,
                "crs_proj4": crs.to_proj4() if crs else None,
                "crs_epsg": crs.to_epsg() if crs else None,
                "width": width,
                "height": height,
                "count": count,
                "dtype": dtype,
            }

            logger.info(f"Successfully read COG metadata from {url}")
            return metadata

    except rasterio.RasterioIOError as e:
        logger.error(f"Failed to read COG from {url}: {e}")
        raise ValueError(f"Invalid or inaccessible COG URL: {url}")
    except Exception as e:
        logger.error(f"Unexpected error reading COG metadata: {e}")
        raise ValueError(f"Error processing COG: {str(e)}")


def generate_qlr(
    metadata: Dict[str, Any],
    url: str,
    layer_id: str,
    layer_name: Optional[str] = None,
    template_path: Optional[str] = None,
) -> str:
    """
    Generate QLR XML from metadata and template.
    """
    if not template_path or not Path(template_path).exists():
        raise ValueError("Template path is required and must exist")

    if layer_name is None:
        layer_name = os.path.basename(url)

    try:
        with open(template_path, "r") as f:
            template = f.read()

        extent = metadata["extent"]
        wgs84_extent = metadata["wgs84_extent"]

        qlr_xml = template.format(
            datasource=f"/vsicurl/{url}",
            layer_id=layer_id,
            layer_name=layer_name,
            xmin=extent.left,
            ymin=extent.bottom,
            xmax=extent.right,
            ymax=extent.top,
            wgs84_xmin=wgs84_extent[0],
            wgs84_ymin=wgs84_extent[1],
            wgs84_xmax=wgs84_extent[2],
            wgs84_ymax=wgs84_extent[3],
            crs_wkt=metadata["crs_wkt"],
            crs_proj4=metadata["crs_proj4"],
            crs_epsg=metadata["crs_epsg"] if metadata["crs_epsg"] is not None else "",
        )

        logger.info(f"Successfully generated QLR for {url}")
        return qlr_xml

    except Exception as e:
        logger.error(f"Failed to generate QLR: {e}")
        raise ValueError(f"Error generating QLR: {str(e)}")


def write_qlr_file(qlr_text: str, output_path: str) -> None:
    """
    Write the QLR XML text to the specified output file with proper error handling.
    """
    try:
        with open(output_path, "w") as f:
            f.write(qlr_text)
        logger.info(f"QLR file written successfully to {output_path}")
    except Exception as e:
        logger.error(f"Failed to write QLR file to {output_path}: {e}")
        raise ValueError(f"Error writing QLR file: {str(e)}")


def create_qlr(url: str, collection: str) -> str:
    """
    Create QLR file for given URL and collection with proper error handling.
    """
    try:
        # Validate inputs
        if not url or not collection:
            raise ValueError("URL and collection are required")

        if not url.strip():
            raise ValueError("URL cannot be empty")

        if not collection.strip():
            raise ValueError("Collection cannot be empty")

        # Get metadata
        metadata = get_cog_metadata(url.strip())

        # Get template path
        template_path = get_template_path(collection.strip())

        # Generate QLR
        layer_name = os.path.basename(url)
        qlr = generate_qlr(metadata, url, layer_name, layer_name, template_path)

        logger.info(f"QLR created successfully for {url} with collection {collection}")
        return qlr

    except Exception as e:
        logger.error(f"QLR creation failed: {e}")
        raise


if __name__ == "__main__":
    # Example usage
    url = "https://dap.ceda.ac.uk/neodc/sentinel_ard/data/sentinel_2/2025/07/02/S2C_20250702_latn528lonw0037_T30UVD_ORB037_20250702133100_utm30n_osgb_vmsk_sharp_rad_srefdem_stdsref.tif"
    qlr = create_qlr(url, "sentinel2_ard")
    print(qlr)
    # Save to file
    output_path = "test_output.qlr"
    write_qlr_file(qlr, output_path)
