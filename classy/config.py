"""User-specific configuration in classy."""

import os
from pathlib import Path

from classy.utils.logging import logger
from platformdirs import user_cache_dir

# Data Directory
if "CLASSY_DATA_DIR" in os.environ:
    PATH_DATA = Path(os.environ["CLASSY_DATA_DIR"]).expanduser().absolute()

    if not PATH_DATA.is_dir():
        raise ValueError(f"Path {PATH_DATA} does not exist.")
else:
    PATH_DATA = Path(user_cache_dir()) / "classy"

logger.debug(f"classy data directory: {PATH_DATA}")

# Maximum missing wavelength range to extrapolate for classification
EXTRAPOLATION_LIMIT = 10  # in percent
