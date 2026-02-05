import os
import PyOpenColorIO as OCIO
import logging
import subprocess

OCIO_FALLBACK = "//vm-fs-001/prod/sww/config/OCIO/config.ocio"

def run_make_tx(options_dict, texture_file):
    """Runs the maketx command with the provided options on a texture file.

    Args:
        options_dict(dict): dictionary of maketx options
        texture_file(str): the texture file to create a tx file from.

    Returns:
        str: returns the string "Success" if process completed successfully, or returns an error code if failed.
    """
    compression = options_dict['compression']
    env_map = ''
    if options_dict['env_map']:
        env_map = ' --envlatl'
    wrap_mode = options_dict['wrap_mode']
    additional_options = options_dict['additional_options']

    tx_settings = f"{additional_options} --oiio --opaque-detect --constant-color-detect --fixnan box3" \
                  f" --monochrome-detect --wrap {wrap_mode}{env_map} --attrib tiff:half 1" \
                  f" --compression {compression} --format exr -d half"
    colorspace_override = options_dict.get('colorspace_override')
    ocio_config = os.getenv("OCIO")
    if not ocio_config:
        ocio_config = OCIO_FALLBACK
    config = OCIO.Config.CreateFromFile(ocio_config)
    OCIO.SetCurrentConfig(config)

    scene_colorspace = config.getColorSpace(OCIO.ROLE_SCENE_LINEAR)
    scene_colorspace = scene_colorspace.getName()
    colorspace = config.parseColorSpaceFromString(texture_file)
    if colorspace_override:
        colorspace = colorspace_override
    if not colorspace:
        colorspace = config.getColorSpace(OCIO.ROLE_DEFAULT).getName()
    colorspace_settings = f'--colorconvert "{colorspace}" "{scene_colorspace}" --colorconfig "{ocio_config}"'

    new_file_name = os.path.splitext(texture_file)[0]+'.tx'
    make_string = f'maketx {tx_settings} {colorspace_settings} -o "{new_file_name}" "{texture_file}"'
    logging.info(make_string)
    try:
        subprocess.run(make_string, capture_output=True, check=True, text=True)
        return "Success"
    except subprocess.CalledProcessError as e:
        return e.output
