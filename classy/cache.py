"""Cache management for classy."""

from pathlib import Path

import numpy as np
import pandas as pd
import rocks

from classy import config
from classy.log import logger
from classy import core


# ------
# Indeces of spectra
def load_index(which):
    """Load an index file."""
    if which == "AKARI":
        return load_akari_index()
    elif which == "Gaia":
        return load_gaia_index()
    elif which == "Mahlke":
        return load_mahlke_index()
    elif which == "SMASS":
        return load_smass_index()
    elif which == "ECAS":
        return load_ecas_index()
    else:
        raise ValueError(
            f"Unknown spectra source '{which}'. Choose one of {classy.data.SOURCES}."
        )


def load_akari_index():
    """Load the Gaia DR3 reflectance spectra index."""

    PATH_INDEX = config.PATH_CACHE / "akari/AcuA_1.0/index.csv"

    if not PATH_INDEX.is_file():
        retrieve_akari_spectra()

    return pd.read_csv(PATH_INDEX, dtype={"number": "Int64"})


def load_ecas_index():
    """Load the Gaia DR3 reflectance spectra index."""

    PATH_INDEX = config.PATH_CACHE / "ecas/ecas_mean.csv"

    if not PATH_INDEX.is_file():
        retrieve_ecas_spectra()

    return pd.read_csv(PATH_INDEX, dtype={"number": "Int64"})


def load_gaia_index():
    """Load the Gaia DR3 reflectance spectra index."""

    PATH_INDEX = config.PATH_CACHE / "gaia/index.csv"

    if not PATH_INDEX.is_file():
        retrieve_gaia_spectra()

    return pd.read_csv(PATH_INDEX, dtype={"number": "Int64"})


def load_smass_index():
    """Load the SMASS reflectance spectra index."""

    PATH_INDEX = config.PATH_CACHE / "smass/index.csv"

    if not PATH_INDEX.is_file():
        logger.info("Retrieving index of SMASS spectra...")

        URL_INDEX = "https://raw.githubusercontent.com/maxmahlke/classy/main/data/smass/index.csv"
        index = pd.read_csv(URL_INDEX)
        PATH_INDEX.parent.mkdir(parents=True, exist_ok=True)
        index.to_csv(PATH_INDEX, index=False)

    return pd.read_csv(PATH_INDEX, dtype={"number": "Int64"})


def load_mahlke_index():
    """Load the index of spectra from Mahlke+ 2022."""
    PATH_INDEX = config.PATH_CACHE / "mahlke/index.csv"
    return pd.read_csv(PATH_INDEX, dtype={"number": "Int64"})


# ------
# Load spectra from cache
def load_spectra(idx_spectra):
    """Load a spectrum from a known source.

    Returns
    -------
    list of classy.core.Spectrum
    """

    spectra = []

    for _, spec in idx_spectra.iterrows():
        if spec.source == "AKARI":
            spec = load_akari_spectrum(spec)
        elif spec.source == "Gaia":
            spec = load_gaia_spectrum(spec)
        elif spec.source == "SMASS":
            spec = load_smass_spectrum(spec)
        elif spec.source == "ECAS":
            spec = load_ecas_spectrum(spec)

        spectra.append(spec)

    return spectra


def load_akari_spectrum(spec):
    """Load a cached AKARI spectrum.

    Parameters
    ----------
    spec : pd.Series

    Returns
    -------
    astro.core.Spectrum

    """
    PATH_SPEC = config.PATH_CACHE / f"akari/AcuA_1.0/reflectance/{spec.filename}"

    # Load spectrum
    data = pd.read_csv(
        PATH_SPEC,
        delimiter="\s+",
        names=[
            "wave",
            "refl",
            "refl_err",
            "flag_err",
            "flag_saturation",
            "flag_thermal",
            "flag_stellar",
        ],
    )

    # Add a joint flag, it's 1 if any other flag is 1
    data["flag"] = data.apply(
        lambda point: 1
        if any(
            bool(point[flag])
            for flag in ["flag_err", "flag_saturation", "flag_thermal", "flag_stellar"]
        )
        else 0,
        axis=1,
    )

    spec = core.Spectrum(
        wave=data.wave.values,
        refl=data.refl.values,
        refl_err=data.refl_err.values,
        flag=data.flag.values,
        source="AKARI",
        name=f"AKARI - {spec['name']}",
        asteroid_name=spec["name"],
        asteroid_number=spec.number,
        reference="Usui+ 2019",
        flag_err=data.flag_err.values,
        flag_saturation=data.flag_saturation.values,
        flag_thermal=data.flag_thermal.values,
        flag_stellar=data.flag_stellar.values,
    )

    return spec


def load_ecas_spectrum(spec):
    """Load a cached ECAS spectrum.

    Parameters
    ----------
    spec : pd.Series

    Returns
    -------
    astro.core.Spectrum
    """
    PATH_SPEC = config.PATH_CACHE / f"ecas/ecas_mean.csv"

    obs = pd.read_csv(PATH_SPEC)
    obs = obs.loc[obs["name"] == spec["name"]]

    # Convert colours to reflectances
    wave = [0.337, 0.359, 0.437, 0.550, 0.701, 0.853, 0.948, 1.041]
    refl = []
    refl_err = []

    for color in ["S_V", "U_V", "B_V"]:
        refl_c = obs[f"{color}_MEAN"].values[0]
        refl.append(np.power(10, -0.4 * (refl_c)))
        re = np.abs(refl_c) * np.abs(
            0.4 * np.log(10) * obs[f"{color}_STD_DEV"].values[0]
        )
        refl_err.append(re)

    refl.append(1)  # v-filter
    refl_err.append(0)  # v-filter

    for color in [
        "V_W",
        "V_X",
        "V_P",
        "V_Z",
    ]:
        refl_c = obs[f"{color}_MEAN"].values[0]
        refl.append(np.power(10, -0.4 * (-refl_c)))
        re = np.abs(refl_c) * np.abs(
            0.4 * np.log(10) * obs[f"{color}_STD_DEV"].values[0]
        )
        refl_err.append(re)

    refl = np.array(refl)

    refl_err = np.array(refl_err)

    spec = core.Spectrum(
        wave=wave,
        refl=refl,
        refl_err=refl_err,
        source="ECAS",
        name=f"ECAS",
        asteroid_name=spec["name"],
        asteroid_number=spec.number,
        nights=obs["NIGHTS"].values[0],
        note=obs["NOTE"].values[0],
    )

    flags = []

    for color in ["S_V", "U_V", "B_V", "V_V", "V_W", "V_X", "V_P", "V_Z"]:
        if color == "V_V":
            flag_value = 0
        else:
            flag_value = int(obs[f"flag_{color}"].values[0])
        setattr(spec, f"flag_{color}", flag_value)
        flags.append(flag_value)

    spec.flag = np.array(flags)
    return spec


def load_gaia_spectrum(spec):
    """Load a cached Gaia spectrum.

    Parameters
    ----------
    spec : pd.Series

    Returns
    -------
    astro.core.Spectrum

    """
    PATH_SPEC = config.PATH_CACHE / f"gaia/{spec.filename}.csv"

    obs = pd.read_csv(PATH_SPEC, dtype={"reflectance_spectrum_flag": int})
    obs = obs.loc[obs["name"] == spec["name"]]

    # Apply correction by Tinaut-Ruano+ 2023
    corr = [1.07, 1.05, 1.02, 1.01, 1.00]
    refl = obs.reflectance_spectrum.values
    refl[: len(corr)] *= corr

    spec = core.Spectrum(
        wave=obs.wavelength.values / 1000,
        wavelength=obs.wavelength.values / 1000,
        refl=refl,
        reflectance_spectrum=refl,
        refl_err=obs.reflectance_spectrum_err.values,
        flag=obs.reflectance_spectrum_flag.values,
        reflectance_spectrum_flag=obs.reflectance_spectrum_flag.values,
        source="Gaia",
        name=f"Gaia",
        asteroid_name=spec["name"],
        asteroid_number=spec.number,
        source_id=obs.source_id.tolist()[0],
        number_mp=obs.source_id.tolist()[0],
        solution_id=obs.solution_id.tolist()[0],
        denomination=obs.denomination.tolist()[0],
        nb_samples=obs.nb_samples.tolist()[0],
        num_of_spectra=obs.num_of_spectra.tolist()[0],
    )

    return spec


def load_smass_spectrum(spec):
    """Load a cached SMASS spectrum."""
    PATH_SPEC = config.PATH_CACHE / f"smass/{spec.inst}/{spec.run}/{spec.filename}"

    if not PATH_SPEC.is_file():
        retrieve_smass_spectrum(spec)

    data = pd.read_csv(PATH_SPEC)

    if spec.run == "smass1":
        data.wave /= 10000

    # 2 - reject. This is flag 0 in SMASS
    flags = [0 if f != 0 else 2 for f in data["flag"].values]

    spec = core.Spectrum(
        wave=data["wave"],
        refl=data["refl"],
        refl_err=data["err"],
        flag=flags,
        source="SMASS",
        run=spec.run,
        inst=spec.inst,
        name=f"{spec.inst}/{spec.run}",
        filename=spec.filename,
        asteroid_name=spec["name"],
        asteroid_number=spec.number,
    )
    return spec


# ------
# Downloading spectra from source
def retrieve_gaia_spectra():
    """Retrieve Gaia DR3 reflectance spectra to cache."""

    logger.info("Retrieving Gaia DR3 reflectance spectra [13MB] to cache...")

    # Create directory structure
    PATH_GAIA = config.PATH_CACHE / "gaia"
    PATH_GAIA.mkdir(parents=True, exist_ok=True)

    # Retrieve observations
    URL = "http://cdn.gea.esac.esa.int/Gaia/gdr3/Solar_system/sso_reflectance_spectrum/SsoReflectanceSpectrum_"

    index = {}

    # Observations are split into 20 parts
    logger.info("Creating index of Gaia spectra...")
    for idx in range(20):
        # Retrieve the spectra
        part = pd.read_csv(f"{URL}{idx:02}.csv.gz", compression="gzip", comment="#")

        # Create list of identifiers from number and name columns
        ids = part.number_mp.fillna(part.denomination).values
        names, numbers = zip(*rocks.id(ids))

        part["name"] = names
        part["number"] = numbers

        # Add to index for quick look-up
        for name, entries in part.groupby("name"):
            # Use the number for identification if available, else the name
            number = entries.number.values[0]
            asteroid = number if number else name

            index[asteroid] = f"SsoReflectanceSpectrum_{idx:02}"

        # Store to cache
        part.to_csv(PATH_GAIA / f"SsoReflectanceSpectrum_{idx:02}.csv", index=False)

    # Convert index to dataframe, store to cache
    names, numbers = zip(*rocks.identify(list(index.keys())))
    index = pd.DataFrame(
        data={"name": names, "number": numbers, "filename": list(index.values())}
    )
    index.to_csv(PATH_GAIA / "index.csv", index=False)


def retrieve_smass_spectrum(spec):
    """Retrieve a SMASS spectra from smass.mit.edu.

    Parameters
    ----------
    spec : pd.Series
        Entry of the SMASS index containing metadata of spectrum to retrieve.

    Notes
    -----
    Spectrum is stored in the cache directory.
    """

    URL_BASE = "http://smass.mit.edu/data"

    # Create directory structure and check if the spectrum is already cached
    PATH_OUT = config.PATH_CACHE / f"smass/{spec.inst}/{spec.run}/{spec.filename}"

    # Ensure directory structure exists
    PATH_OUT.parent.mkdir(parents=True, exist_ok=True)

    # Download spectrum
    URL = f"{URL_BASE}/{spec.inst}/{spec.run}/{spec.filename}"
    obs = pd.read_csv(URL, delimiter="\s+", names=["wave", "refl", "err", "flag"])

    # Store to file
    obs.to_csv(PATH_OUT, index=False)
    logger.info(f"Retrieved spectrum {spec.run}/{spec.filename} from SMASS")


def retrieve_akari_spectra():
    """Download the AcuA-spec archive to cache."""

    import tarfile
    import requests

    URL = "https://darts.isas.jaxa.jp/pub/akari/AKARI-IRC_Spectrum_Pointed_AcuA_1.0/AcuA_1.0.tar.gz"
    PATH_AKARI = config.PATH_CACHE / "akari"

    PATH_AKARI.mkdir(parents=True, exist_ok=True)

    # Retrieve spectra
    logger.info("Retrieving AKARI AcuA-spec reflectance spectra [1.7MB] to cache...")
    with requests.get(URL, stream=True) as file_:
        with tarfile.open(fileobj=file_.raw, mode="r:gz") as archive:
            archive.extractall(PATH_AKARI)

    # Create index
    index = pd.read_csv(
        PATH_AKARI / "AcuA_1.0/target.txt",
        delimiter="\s+",
        names=["number", "name", "obs_id", "date", "ra", "dec"],
        dtype={"number": int},
    )
    index = index.drop_duplicates("number")

    # Drop (4) Vesta and (4015) Wilson-Harrington as there are no spectra of them
    index = index[~index.number.isin([4, 15])]

    # Add filenames
    index["filename"] = index.apply(
        lambda row: f"{row.number:>04}_{row['name']}.txt", axis=1
    )

    index.to_csv(PATH_AKARI / "AcuA_1.0/index.csv", index=False)


def retrieve_ecas_spectra():
    """Download the Eight Color Asteroid Survey results from PDS to cache."""
    from io import BytesIO
    from zipfile import ZipFile

    import requests

    PATH_ECAS = config.PATH_CACHE / "ecas"
    PATH_ECAS.mkdir(parents=True, exist_ok=True)

    URL = "https://sbnarchive.psi.edu/pds4/non_mission/gbo.ast.ecas.phot.zip"
    logger.info("Retrieving Eight Color Asteroid Survey results [130kB] to cache...")

    content = requests.get(URL)

    # unzip the content
    f = ZipFile(BytesIO(content.content))

    # extract mean colors
    mean = "gbo.ast.ecas.phot/data/ecasmean.tab"
    scores = "gbo.ast.ecas.phot/data/ecaspc.tab"

    f.extract(mean, PATH_ECAS)
    f.extract(scores, PATH_ECAS)
    path_mean = PATH_ECAS / mean
    path_scores = PATH_ECAS / scores

    mean = pd.read_fwf(
        path_mean,
        colspecs=[
            (0, 6),
            (7, 24),
            (24, 30),
            (31, 34),
            (35, 41),
            (42, 45),
            (46, 52),
            (53, 56),
            (57, 63),
            (64, 67),
            (68, 74),
            (75, 78),
            (79, 85),
            (86, 89),
            (90, 96),
            (97, 100),
            (101, 102),
            (103, 105),
        ],
        names=[
            "AST_NUMBER",
            "AST_NAME",
            "S_V_MEAN",
            "S_V_STD_DEV",
            "U_V_MEAN",
            "U_V_STD_DEV",
            "B_V_MEAN",
            "B_V_STD_DEV",
            "V_W_MEAN",
            "V_W_STD_DEV",
            "V_X_MEAN",
            "V_X_STD_DEV",
            "V_P_MEAN",
            "V_P_STD_DEV",
            "V_Z_MEAN",
            "V_Z_STD_DEV",
            "NIGHTS",
            "NOTE",
        ],
    )

    names, numbers = zip(*rocks.id(mean.AST_NUMBER))

    mean["name"] = names
    mean["number"] = numbers

    # Set saturated or missing colors to NaN
    mean = mean.replace(-9.999, np.nan)
    mean["flag"] = 0

    for unc in [
        "S_V_STD_DEV",
        "U_V_STD_DEV",
        "B_V_STD_DEV",
        "V_W_STD_DEV",
        "V_X_STD_DEV",
        "V_P_STD_DEV",
        "V_Z_STD_DEV",
    ]:
        mean[unc] /= 1000

    mean.loc[
        (mean.S_V_STD_DEV > 0.095)
        | (mean.U_V_STD_DEV > 0.074)
        | (mean.B_V_STD_DEV > 0.039)
        | (mean.V_W_STD_DEV > 0.034)
        | (mean.V_X_STD_DEV > 0.039)
        | (mean.V_P_STD_DEV > 0.044)
        | (mean.V_Z_STD_DEV > 0.051),
        "flag",
    ] = 1

    for color, limit in zip(
        [
            "S_V_STD_DEV",
            "U_V_STD_DEV",
            "B_V_STD_DEV",
            "V_W_STD_DEV",
            "V_X_STD_DEV",
            "V_P_STD_DEV",
            "V_Z_STD_DEV",
        ],
        [0.095, 0.074, 0.039, 0.034, 0.039, 0.044, 0.051],
    ):
        mean.loc[mean[color] > limit, f"flag_{color[:3]}"] = 1
        mean.loc[mean[color] <= limit, f"flag_{color[:3]}"] = 0
    # Add quality flag following Tholen+ 1984
    mean.to_csv(PATH_ECAS / "ecas_mean.csv", index=False)

    # TODO Add tholen classifcation resutls parsing
    scores = pd.read_fwf(
        path_scores,
        colspecs=[
            (0, 6),
            (7, 25),
            (26, 32),
            (33, 39),
            (40, 46),
            (47, 53),
            (54, 60),
            (61, 67),
            (68, 74),
            (75, 76),
        ],
        names=[
            "AST_NUMBER",
            "AST_NAME",
            "PC1",
            "PC2",
            "PC3",
            "PC4",
            "PC5",
            "PC6",
            "PC7",
            "NOTE",
        ],
    )

    names, numbers = zip(*rocks.identify(scores.AST_NAME))

    scores["name"] = names
    scores["number"] = numbers

    for ind, row in scores.iterrows():
        r = rocks.Rock(row["name"], datacloud="taxonomies")
        class_ = r.taxonomies[r.taxonomies.shortbib == "Tholen+1989"]
        class_ = class_.class_.values[0]
        scores.loc[ind, "class_"] = class_

    # Remove (152) Atala as it was misidentified in ECAS and thus has NaN scores
    scores = scores.replace(-9.999, np.nan).dropna(subset="PC1")
    scores.to_csv(PATH_ECAS / "ecas_scores.csv", index=False)


if __name__ == "__main__":
    retrieve_ecas_spectra()
