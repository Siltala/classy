"""Classification of asteroids following Tholen 1984."""
from functools import cache

from classy import cache
from classy import config
from classy.log import logger

# ------
# Defintions

# Central wavelengths of the ECAS colours
WAVE = [0.337, 0.359, 0.437, 0.550, 0.701, 0.853, 0.948, 1.041]

# Mean and standard deviation of ECAS colours, Tholen 1984 Table II
ECAS_MEAN = [0.325, 0.234, 0.089, 0.091, 0.105, 0.103, 0.111]
ECAS_STD = [0.221, 0.173, 0.092, 0.081, 0.091, 0.104, 0.120]


# Eigenvalues and eigenvectors of PCA, Tholen 1984 Table IV
EIGENVALUES = [4.737, 1.879, 0.180, 0.118, 0.045, 0.032, 0.010]
EIGENVECTORS = [
    [0.346, 0.373, 0.415, 0.433, 0.399, 0.336, 0.330],
    [-0.463, -0.416, -0.289, 0.000, 0.320, 0.475, 0.448],
    [0.231, 0.207, 0.028, -0.622, -0.290, -0.002, 0.657],
    [-0.207, -0.103, 0.028, 0.586, -0.399, -0.460, 0.481],
    [0.442, 0.044, -0.707, 0.094, 0.398, -0.347, 0.124],
    [-0.303, -0.039, 0.398, -0.271, 0.580, -0.574, 0.100],
    [0.531, -0.795, 0.292, -0.016, -0.010, -0.022, 0.031],
]

# ------
# Functions for classification
@cache
def load_classification():
    """Load the Tholen 1984 classification results like PC scores and classes from file.

    Returns
    -------
    pd.DataFrame
        The classification results of the 405 high-quality ECAS observations.
    """

    # Launch same ECAS method if data not present
    PATH_DATA = config.PATH_CACHE / "ecas/ecas_scores.csv"

    if not PATH_DATA.is_file():
        cache.retrieve_ecas_spectra()

    return pd.read_csv(PATH_DATA, dtype={"number": "Int64"})


def decision_tree(spec):
    """Decision tree to identify taxonomic class in Tholen 1984 system.

    Parameters
    ----------
    spec : classy.Spectrum
        The spectrum to classify.

    Returns
    -------
    str
        The Tholen classification of this spectrum.
    """

    # Load the PCs of all ECAS asteroids
    tholen = load_classification()
    tholen_scores = tholen[["PC1", "PC2", "PC3", "PC4", "PC5", "PC6", "PC7"]].values

    # Find the classification of the closest asteroid in PC space
    distances = [
        np.linalg.norm(spec.tholen_scores - ecas_scores)
        for ecas_scores in tholen_scores
    ]
    class_ = tholen.loc[np.argmin(distances), "class_"]

    # Resolve ambiguity the simple way
    if len(class_) == 2:
        class_ = class_[0]

    # Pass through albedo decision tree
    if class_ in ["E", "M", "P", "X"]:
        if np.isnan(spec.pV):
            return "X"
        elif -2.5 * np.log10(spec.pV) > 3:
            return "P"
        elif -2.5 * np.log10(spec.pV) > 1.4:
            return "M"
        return "E"

    if class_ in ["C", "F", "B", "G"]:
        if -2.5 * np.log10(spec.pV) <= 1.4:
            return "E"

    if class_ in ["C", "B"]:
        if -2.5 * np.log10(spec.pV) > 3:
            return "C"
        return "B"

    return class_


# ------
# Functions for plotting
def plot_pc_space(ax, spectra):
    """Plot the distribution of classified spectra and the ECAS spectra in the Tholen PC space.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The matplotlib axis instance to plot to.
    spectra : classy.Spectra or list of classy.Spectrum
        One or more spectra which were previously classified in the Tholen system.

    Returns
    -------
    matplotlib.axes.Axes
        The matplotlib axis with the plotted classification results.
    """

    opts_text = dict(va="center", ha="center", clip_on=True)

    # ------
    # Add the distribution of the ECAS asteroids
    tholen = load_classification()

    for _, ast in tholen.iterrows():

        # Dummy to ensure proper plot limits
        ax.scatter(ast.PC1, ast.PC2, alpha=0)

        # Add asteroid position in PC space represented by its number
        ax.text(ast.PC1, ast.PC2, str(ast.number), color="lightgray", **opts_text)

    # ------
    # Add the mean positions of the main classes
    for class_, pcs in tholen.groupby("class_"):

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

        if not spec.class_tholen:
            logger.warning(f"[{spec.name}]: Not classifiend in Tholen 1984 system.")
            continue

        ax.scatter(
            spec.tholen_scores[0],
            spec.tholen_scores[1],
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
