"""Classification of asteroids following DeMeo+ 2009."""
from functools import lru_cache

import numpy as np
import pandas as pd

from classy import cache
from classy import config
from classy.log import logger


def is_classifiable(spec):
    """Check if spectrum can be classified based on the wavelength range.

    Parameters
    ----------
    taxonomy : str
        The taxonomic scheme to check.

    Returns
    -------
    bool
        True if the spectrum can be classified, else False.
    """
    if spec.wave.min() > WAVE.min() or spec.wave.max() < WAVE.max():
        logger.debug(
            f"[{spec.name}]: Insufficient wavelength range for DeMeo taxonomy ({spec.wave.min()} - {spec.wave.max()})"
        )
        return False
    return True


# ------
# Functions for preprocessing
def preprocess(spec, smooth=False):
    """Preprocess a spectrum for classification following DeMeo+ 2009.

    Parameters
    ----------
    spec : classy.Spectrum
        The spectrum to preprocess.
    smooth : bool
        Whether the spectrum should be smoothed. Default is False.

    Returns
    ----------
    classy.Spectrum
        The preprocessed spectrum.

    Notes
    -----
    Preprocessing steps include smoothing, slope removal, renormalization, and resampling.
    """

    # Smooth
    if smooth:
        spec.smooth()

    # Remove slope and renormalize
    spec.normalize(at=0.55)
    spec.remove_slope(translate_to=0.55)

    # Resample to DeMeo+ 2009 wavelength grid
    spec.resample(WAVE)
    breakpoint()

    spec.is_preprocessed_demeo = True


# ------
# Functions for classification
def classify(spec):
    """Classify a spectrum in the system of DeMeo+ 2009.

    Parameters
    ----------
    spec : classy.Spectrum
        The spectrum to classify.

    Returns
    ----------
    classy.Spectrum
        The spectrum which added classification attributes: ['class_demeo', 'scores_demeo'].
    """

    # Check if it can be classified in this scheme
    # Check if it has been preprocessed for this scheme

    if not spec.is_preprocessed_demeo:
        logger.warning(
            f"[{spec.name}]: Classifying following DeMeo+ 2009 but not preprocessed yet."
        )

        if spec.wave != WAVE:
            raise ValueError(
                f"[{spec.name}]: The wavelength bins do not match the DeMeo+ 2009 sampling."
            )

    # Extract the reflectance and demean following DeMeo+ 2009
    refl = np.concatenate([spec.refl[:2], spec.refl[3:]])
    breakpoint()
    refl -= DATA_MEAN.T

    # Compute scores
    spec.scores_demeo = EIGENVECTORS @ data.T

    # And compute the class
    spec.class_demeo = decision_tree(spec)
    add_classification_results(spec)


def decision_tree(spec):
    """Implements the class decision tree given in Table B in Appendix B of DeMeo+ 2009."""

    # Align with DeMeo's notation but dropping the '
    pc1, pc2, pc3, pc4 = spec.scores_demeo[:4]
    # pc1 = spec.pc0_demeo
    # pc2 = spec.pc1_demeo
    # pc3 = spec.pc2_demeo
    # pc4 = spec.pc3_demeo
    slope = spec.slope[0]

    # Lines
    alpha = lambda pc2: -3 * pc2 - 0.28  # = pc1
    beta = lambda pc2: -3 * pc2 + 0.35  # = pc1
    gamma = lambda pc2: -3 * pc2 + 1.0  # = pc1
    delta = lambda pc2: -3 * pc2 + 1.5  # = pc1
    epsilon = lambda pc2: 1 / 3 * pc2 + 0.55  # = pc1
    zeta = lambda pc2: 1 / 3 * pc2 - 0.10  # = pc1
    eta = lambda pc2: 1 / 3 * pc2 - 0.40  # = pc1
    theta = lambda pc2: -3 * pc2 + 0.7  # = pc1

    # Vis-IR step 1
    if (pc1 < -0.3) and (pc2 >= 0.2) and (slope >= 0.4):
        if 0.55 <= slope < 1.5:
            spec.class_demeo = "A"
            return
        elif 0.4 <= slope < 0.55:
            spec.class_demeo = "Sa"
            return
        else:
            classy.logging.logger.warning(
                "DeMeo class is indeterminate after VisIR step 1"
            )
            spec.class_demeo = ""

    # Vis-IR step 2
    if pc1 > alpha(pc2):  # lies above alpha line
        if pc1 >= gamma(pc2):
            if slope >= 0.25:
                spec.class_demeo = "Vw"
                return
            else:
                spec.class_demeo = "V"
                return
        if pc1 <= eta(pc2) and pc1 >= theta(pc2) and pc1 < delta(pc2):
            spec.class_demeo = "O"
            return
        if pc1 <= eta(pc2) and pc1 >= alpha(pc2) and pc1 < theta(pc2):
            if slope >= 0.25:
                spec.class_demeo = "Qw"
                return
            else:
                spec.class_demeo = "Q"
                return
        if pc1 >= eta(pc2) and pc1 >= gamma(pc2) and pc1 < delta(pc2):
            spec.class_demeo = "R"
            return
        return demeo_s_complex(spec)

    # Vis-IR step 3
    if 0.38 <= slope < 1.5 and -0.44 < pc1 < 0.4:
        spec.class_demeo = "D"
        classy.logging.logger.warning(
            f"{spec.name}: DeMeo+ 09 class is either D (no 1mu feature) or A type (1 mu feature)"
        )
        return

    if 0.25 < slope < 0.38 and -0.28 < pc2 < -0.2 and -0.2 < pc3 < -0.12:
        spec.class_demeo = "T"
        return

    if 0.07 < pc1 < 1.0 and -0.5 < pc2 < -0.15:
        spec.class_demeo = "L"
        classy.logging.logger.warning(
            f"{spec.name}: DeMeo+ 09 class is either L (no 0.49mu feature) or Xe type (0.49 mu feature)"
        )
        return

    if -0.075 < pc3 < 0.14 and -0.2 <= pc2 < -0.1 and -0.8 < pc1 < -0.1:
        spec.class_demeo = "K"
        classy.logging.logger.warning(
            f"{spec.name}: DeMeo+ 09 class is either K (no 0.49mu feature) or Xe type (0.49 mu feature)"
        )
        return

    return demeo_c_and_x_complexes(spec)


def demeo_s_complex(spec):

    # Align with DeMeo's notation but dropping the '
    pc1 = spec.pc0_demeo
    pc2 = spec.pc1_demeo
    pc3 = spec.pc2_demeo
    pc4 = spec.pc3_demeo
    slope = spec.slope[0]

    # Lines
    alpha = lambda pc2: -3 * pc2 - 0.28  # = pc1
    beta = lambda pc2: -3 * pc2 + 0.35  # = pc1
    gamma = lambda pc2: -3 * pc2 + 1.0  # = pc1
    delta = lambda pc2: -3 * pc2 + 1.5  # = pc1
    epsilon = lambda pc2: 1 / 3 * pc2 + 0.55  # = pc1
    zeta = lambda pc2: 1 / 3 * pc2 - 0.10  # = pc1
    eta = lambda pc2: 1 / 3 * pc2 - 0.40  # = pc1
    theta = lambda pc2: -3 * pc2 + 0.7  # = pc1

    if pc1 < beta(pc2) and pc1 > delta(pc2):
        if slope >= 0.25:
            spec.class_demeo = "Sw"
            return
        else:
            spec.class_demeo = "S"
            return
    if pc1 >= alpha(pc2) and pc1 < beta(pc2) and pc1 > eta(pc2) and pc1 <= zeta(pc2):
        if slope >= 0.25:
            spec.class_demeo = "Sqw"
            return
        else:
            spec.class_demeo = "Sq"
            return
    if pc1 >= beta(pc2) and pc1 < gamma(pc2) and pc1 > eta(pc2) and pc1 <= epsilon(pc2):
        if slope >= 0.25:
            spec.class_demeo = "Srw"
            return
        else:
            spec.class_demeo = "Sr"
            return
    if pc1 >= beta(pc2) and pc1 > epsilon(pc2) and pc1 < gamma(pc2):
        if slope >= 0.25:
            spec.class_demeo = "Svw"
            return
        else:
            spec.class_demeo = "Sv"
            return

    spec.class_demeo = "S"
    classy.logging.logger.warning(
        "DeMeo class is indeterminate S-complex member after VisIR resolution"
    )
    return


def demeo_c_and_x_complexes(spec):

    # Align with DeMeo's notation but dropping the '
    pc1 = spec.pc0_demeo
    pc2 = spec.pc1_demeo
    pc3 = spec.pc2_demeo
    pc4 = spec.pc3_demeo
    pc5 = spec.pc4_demeo
    slope = spec.slope[0]

    # Lines
    alpha = lambda pc2: -3 * pc2 - 0.28  # = pc1
    beta = lambda pc2: -3 * pc2 + 0.35  # = pc1
    gamma = lambda pc2: -3 * pc2 + 1.0  # = pc1
    delta = lambda pc2: -3 * pc2 + 1.5  # = pc1
    epsilon = lambda pc2: 1 / 3 * pc2 + 0.55  # = pc1
    zeta = lambda pc2: 1 / 3 * pc2 - 0.10  # = pc1
    eta = lambda pc2: 1 / 3 * pc2 - 0.40  # = pc1
    theta = lambda pc2: -3 * pc2 + 0.7  # = pc1

    if -0.2 < slope < 0 and -1.2 < pc1 < 0 and pc4 < 0:
        spec.class_demeo = "B"
        return
    if 0.2 < slope < 0.38:
        spec.class_demeo = "X"
        classy.logging.logger.warning(
            f"{spec.name}: DeMeo+ 09 class is either X (no feature), Xk (0.8-1mu feature), Xe (0.49 mu feature), or C (1-1.3mu feature)"
        )
        return
    if 0.01 < pc4 < 0.14 and -0.75 < pc1 < -0.27 and spec.refl[0] < 0.92:
        if spec.wave[0] != 0.45:
            print("First wavelength bin has to be at 0.45mu in DeMeo classification.")
            spec.class_demeo = ""
            return
        spec.class_demeo = "Cgh"
        classy.logging.logger.warning(
            f"{spec.name}: DeMeo+ 09 class is either Cgh (feature at 0.7mu) or Xk (0.8-1mu feature)"
        )
        return
    if 0.01 < pc4 < 0.14 and -0.75 < pc1 < -0.27:
        spec.class_demeo = "Ch"
        classy.logging.logger.warning(
            f"{spec.name}: DeMeo+ 09 class is either Ch (feature at 0.7mu) or Xk (0.8-1mu feature)"
        )
        return
    if -0.04 < pc4 < 0.02 and -0.07 < pc5 < -0.04:
        spec.class_demeo = "Cb"
        return
    if -0.85 < pc1 < -0.45 and -0.06 < pc5 < -0.02:
        spec.class_demeo = "C"
        classy.logging.logger.warning(
            f"{spec.name}: DeMeo+ 09 class is either C (no feature), Ch (feature at 0.7mu), or Xk (0.8-1mu feature)"
        )
        return
    if 0.02 <= pc5 < 0.1 and -0.6 < pc1 < -0.16:
        spec.class_demeo = "Cg"
        classy.logging.logger.warning(
            f"{spec.name}: DeMeo+ 09 class is either Cg (no feature), Cgh (feature at 0.7mu), or Xk (0.8-1mu feature)"
        )
        return
    if -0.45 <= pc1 < 0.1 and -0.06 < pc5 < 0.05:
        spec.class_demeo = "Xk"
        classy.logging.logger.warning(
            f"{spec.name}: DeMeo+ 09 class is either Xk, Xc, Xe, X, Ch."
        )
        return
    if -0.1 <= pc1 < 0.3 and -0.5 < pc2 < -0.2:
        spec.class_demeo = "Xe"
        classy.logging.logger.warning(
            f"{spec.name}: DeMeo+ 09 class is either Xe or L."
        )
        return
    spec.class_demeo = ""
    classy.logging.logger.warning(
        "DeMeo class is indeterminate C/X-complex member after VisIR resolution"
    )
    return


def add_classification_results(spec, results=None):
    pass


# ------
# Functions for plotting
# Functions for classification
@lru_cache(maxsize=None)
def load_classification():
    """Load the DeMeo+ 2009 classification results like PC scores and classes from file.

    Returns
    -------
    pd.DataFrame
        The classification results of the 371 SMASS spectra.
    """

    # Launch same ECAS method if data not present
    PATH_DATA = config.PATH_CACHE / "demeo2009/scores.csv"

    print("Implement data retrieval method")
    # if not PATH_DATA.is_file():
    # cache.retrieve_ecas_spectra()

    return pd.read_csv(PATH_DATA, dtype={"number": "Int64"})


def plot_pc_space(ax, spectra):
    """Plot the distribution of classified spectra and the SMASS spectra in the DeMeo PC space.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The matplotlib axis instance to plot to.
    spectra : classy.Spectra or list of classy.Spectrum
        One or more spectra which were previously classified in the DeMeo system.

    Returns
    -------
    matplotlib.axes.Axes
        The matplotlib axis with the plotted classification results.
    """

    opts_text = dict(va="center", ha="center", clip_on=True)

    # ------
    # Add the distribution of the ECAS asteroids
    demeo = load_classification()

    for _, ast in demeo.iterrows():
        # Dummy to ensure proper plot limits
        ax.scatter(ast.PC1, ast.PC2, alpha=0)

        # Add asteroid position in PC space represented by its number
        ax.text(ast.PC1, ast.PC2, str(ast.number), color="lightgray", **opts_text)

    # ------
    # Add the mean positions of the main classes
    for class_, pcs in demeo.groupby("class_"):
        # Only add the core classe
        if len(class_) > 1:
            continue

        pc0 = np.mean(pcs.PC1)
        pc1 = np.mean(pcs.PC2)

        # Small offsets for readability
        if class_ == "E":
            pc0 += 0.05
        elif class_ == "P":
            pc0 += 0.09

        # Add class indicator
        ax.text(pc0, pc1, class_, size=14, color="black", **opts_text)

    # ------
    # Add classified spectra
    for spec in spectra:
        if not spec.class_demeo:
            logger.warning(f"[{spec.name}]: Not classifiend in DeMeo+ 2009 system.")
            continue

        ax.scatter(
            spec.scores_tholen[0],
            spec.scores_tholen[1],
            marker="d",
            c=spec.color,
            s=40,
            label=f"{spec.name}: {spec.class_tholen}",
            zorder=100,
        )

    # ------
    # Final additions et voila
    ax.axvline(0, ls=":", c="gray")
    ax.axhline(0, ls=":", c="gray")
    ax.legend()

    return ax


# ------
# Defintions

# Central wavelengths of the VisNIR spectra
WAVE = np.arange(0.45, 2.5, 0.05)

# Data mean of DeMeo+ 09 reflectance spectra
# fmt: off
DATA_MEAN = np.array(
    [
        0.8840578, 0.94579985, 1.04016798, 1.07630094, 1.10387232, 1.10729138, 1.07101476, 1.02252107,
        0.99167561, 0.98766575, 1.00292349, 1.02223844, 1.04660108, 1.07201578, 1.08967345, 1.10014259,
        1.11101667, 1.12359452, 1.13128556, 1.13642896, 1.13467689, 1.12810013, 1.11471935, 1.09802574,
        1.07842635, 1.06127665, 1.04536074, 1.03360292, 1.02395605, 1.01587389, 1.01034821, 1.00915786,
        1.01078308, 1.01245031, 1.01298133, 1.01314109, 1.01236654, 1.01140562, 1.01090655, 1.00955344,
    ]
)
# fmt: on

# fmt: off
EIGENVECTORS = np.array(
    [
        [-0.0766, -0.0391, 0.0438, 0.0876, 0.1256, 0.1466, 0.1271, 0.0888, 0.0680, 0.0857, 0.1371,
          0.1921, 0.2322, 0.2566, 0.2704, 0.2787, 0.2849, 0.2852, 0.2782, 0.2641, 0.2427, 0.2154,
          0.1841, 0.1531, 0.1247, 0.1002, 0.0804, 0.0665, 0.0570, 0.0513, 0.0502, 0.0538, 0.0607,
          0.0690, 0.0778, 0.0859, 0.0934, 0.0997, 0.1050, 0.1090,
        ],
        [ -0.0643, -0.0279, 0.0176, 0.0343, 0.0471, 0.0096, -0.1186, -0.2673, -0.3645, -0.3743,
          -0.2899, -0.1527, -0.0381, 0.0306, 0.0708, 0.1053, 0.1385, 0.1598, 0.1645, 0.1520,
           0.1192, 0.0689, 0.0089, -0.0514, -0.1069, -0.1532, -0.1884, -0.2136, -0.2283, -0.2317,
          -0.2233, -0.2023, -0.1706, -0.1302, -0.0852, -0.0406, 0.0023, 0.0438, 0.0832, 0.1177,
        ],
        [ -0.2724, -0.1270, 0.1128, 0.2104, 0.2726, 0.2475, 0.1486, 0.0420, -0.0385, -0.1168,
          -0.2083, -0.2809, -0.2747, -0.2169, -0.1713, -0.1427, -0.1031, -0.0407, 0.0243, 0.0930,
           0.1562, 0.2021, 0.2231, 0.2215, 0.2043, 0.1784, 0.1508, 0.1225, 0.0923, 0.0617, 0.0346,
           0.0136, -0.0038, -0.0229, -0.0447, -0.0678, -0.0911, -0.1153, -0.1389, -0.1580,
        ],
        [  0.3046, 0.1525, -0.1486, -0.2677, -0.3386, -0.3284, -0.2392, -0.1453, -0.0921, -0.0505,
          -0.0289, -0.0277, -0.0160, 0.0077, 0.0304, 0.0450, 0.0608, 0.0842, 0.1104, 0.1387, 0.1609,
           0.1752, 0.1804, 0.1714, 0.1550, 0.1421, 0.1279, 0.1095, 0.0868, 0.0610, 0.0358, 0.0103,
          -0.0162, -0.0476, -0.0838, -0.1225, -0.1644, -0.2068, -0.2445, -0.2708,
        ],
        [ -0.5174, -0.1876, 0.0593, 0.0754, 0.0523, -0.0231, -0.1466, -0.2569, -0.2293, -0.0657, 0.1077,
           0.1717, 0.1685, 0.1611, 0.1463, 0.1061, 0.0533, 0.0090, -0.0429, -0.0868, -0.1188, -0.1250,
          -0.1158, -0.0940, -0.0757, -0.0525, -0.0271, 0.0104, 0.0473, 0.0785, 0.1050, 0.1249, 0.1241,
           0.0916, 0.0354, -0.0327, -0.1126, -0.1993, -0.2884, -0.3767,
        ],
    ]
)
# fmt: on
