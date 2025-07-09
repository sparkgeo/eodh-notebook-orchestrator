import rasterio
from rasterio.warp import transform_bounds
from get_template import get_template_path


def get_cog_metadata(url):
    """
    Reads a COG's metadata from a given URL.
    Returns a dictionary with extent, wgs84_extent, crs info, width, height, band count, and dtype.
    """
    with rasterio.open(url) as src:
        bounds = src.bounds
        crs = src.crs
        width = src.width
        height = src.height
        count = src.count
        dtype = src.dtypes[0]
        # Transform bounds to WGS84
        wgs84_bounds = transform_bounds(crs, "EPSG:4326", *bounds)
        crs_wkt = crs.to_wkt() if crs else None
        crs_proj4 = crs.to_proj4() if crs else None
        crs_epsg = crs.to_epsg() if crs else None
        return {
            "extent": bounds,
            "wgs84_extent": wgs84_bounds,
            "crs_wkt": crs_wkt,
            "crs_proj4": crs_proj4,
            "crs_epsg": crs_epsg,
            "width": width,
            "height": height,
            "count": count,
            "dtype": dtype,
        }


def generate_qlr(metadata, url, layer_id, layer_name=None, template_path=None):
    """
    Fills the QLR template with metadata and returns the QLR XML as text.
    Reads the template from template_path (default: qlr_template.xml in the same directory).
    """
    import os

    if layer_name is None:
        layer_name = os.path.basename(url)
    extent = metadata["extent"]
    wgs84_extent = metadata["wgs84_extent"]
    crs_wkt = metadata["crs_wkt"]
    crs_proj4 = metadata["crs_proj4"]
    crs_epsg = metadata["crs_epsg"]
    if template_path is None:
        raise ValueError("template_path is required")
    with open(template_path, "r") as f:
        template = f.read()
    return template.format(
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
        crs_wkt=crs_wkt,
        crs_proj4=crs_proj4,
        crs_epsg=crs_epsg if crs_epsg is not None else "",
    )


def write_qlr_file(qlr_text, output_path):
    """
    Writes the QLR XML text to the specified output file.
    """
    with open(output_path, "w") as f:
        f.write(qlr_text)


def create_qlr(url, collection):
    meta = get_cog_metadata(url)
    template_path = get_template_path(collection)
    qlr = generate_qlr(meta, url, "test", "test", template_path=template_path)
    return qlr


if __name__ == "__main__":
    # Example usage
    url = "https://dap.ceda.ac.uk/neodc/sentinel_ard/data/sentinel_2/2025/07/02/S2C_20250702_latn528lonw0037_T30UVD_ORB037_20250702133100_utm30n_osgb_vmsk_sharp_rad_srefdem_stdsref.tif"
    qlr = create_qlr(url, "sentinel2_ard")
    print(qlr)
    # Save to file
    output_path = "test_output.qlr"
    write_qlr_file(qlr, output_path)
