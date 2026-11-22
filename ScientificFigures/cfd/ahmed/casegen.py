"""Emit a complete OpenFOAM v2512 simpleFoam case for the Ahmed body.

Usage: python casegen.py <workroot> <slant:25|35> <preset:smoke|prod> [endTime]
"""

import shutil
import sys
from pathlib import Path

U_INF = 40.0
NU = 1.5e-5
RHO_INF = 1.225
AREF = 0.112
LREF = 1.044
CMU = 0.09


def ti_values(ti: float, mixlen: float) -> tuple[float, float, float]:
    """Inlet k, omega and the resulting freestream nut/nu ratio."""
    k = 1.5 * (U_INF * ti) ** 2
    omega = k**0.5 / (CMU**0.25 * mixlen)
    return k, omega, (k / omega) / NU


# baseline used by the original prod runs: I=1%, l=0.01 m -> nut/nu ~ 179
K_INLET, OMEGA_INLET, NUT_RATIO = ti_values(0.01, 0.01)

X_MIN, X_MAX = -3.0, 8.0
Y_MIN, Y_MAX = -2.0, 2.0
Z_MIN, Z_MAX = 0.0, 3.0
BASE_CELL = 0.1

HEADER = """FoamFile
{
    version     2.0;
    format      ascii;
    class       %s;
    object      %s;
}
"""

PRESETS = {
    "smoke": {
        "surface_level": "(2 3)",
        "feature_level": 3,
        "wake_level": 2,
        "near_level": 2,
        "ground_level": 1,
        "layers": 3,
        "ground_layers": 0,
        "max_global": 2000000,
        "end_time": 300,
        "write_interval": 100,
    },
    "prod": {
        "surface_level": "(3 4)",
        "feature_level": 4,
        "wake_level": 3,
        "near_level": 2,
        "ground_level": 2,
        "layers": 6,
        "ground_layers": 0,
        "max_global": 8000000,
        "end_time": 1200,
        "write_interval": 200,
    },
    # slant + wake one level finer, tighter wake box to keep the count near 3M
    "fine": {
        "surface_level": "(4 4)",
        "feature_level": 4,
        "wake_level": 4,
        "near_level": 3,
        "ground_level": 3,
        "layers": 8,
        "ground_layers": 0,
        "boxes": {
            "wakeBox": ((0.8, -0.30, 0.0), (2.2, 0.30, 0.50)),
            "nearBox": ((-0.3, -0.35, 0.0), (1.5, 0.35, 0.50)),
            "groundBox": ((-0.5, -0.50, 0.0), (2.6, 0.50, 0.12)),
        },
        "max_global": 12000000,
        "end_time": 1500,
        "write_interval": 300,
    },
}

DEFAULT_BOXES = {
    "wakeBox": ((0.8, -0.40, 0.0), (3.5, 0.40, 0.70)),
    "nearBox": ((-0.4, -0.45, 0.0), (1.6, 0.45, 0.60)),
    "groundBox": ((-0.5, -0.50, 0.0), (3.0, 0.50, 0.15)),
}


def box_str(p: dict, name: str) -> str:
    lo, hi = p.get("boxes", DEFAULT_BOXES)[name]
    return " ".join(str(v) for v in lo), " ".join(str(v) for v in hi)


def w(path: Path, cls: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER % (cls, path.name) + body, encoding="utf-8", newline="\n")


def block_mesh(case: Path) -> None:
    nx = int(round((X_MAX - X_MIN) / BASE_CELL))
    ny = int(round((Y_MAX - Y_MIN) / BASE_CELL))
    nz = int(round((Z_MAX - Z_MIN) / BASE_CELL))
    w(
        case / "system/blockMeshDict",
        "dictionary",
        f"""
vertices
(
    ({X_MIN} {Y_MIN} {Z_MIN})
    ({X_MAX} {Y_MIN} {Z_MIN})
    ({X_MAX} {Y_MAX} {Z_MIN})
    ({X_MIN} {Y_MAX} {Z_MIN})
    ({X_MIN} {Y_MIN} {Z_MAX})
    ({X_MAX} {Y_MIN} {Z_MAX})
    ({X_MAX} {Y_MAX} {Z_MAX})
    ({X_MIN} {Y_MAX} {Z_MAX})
);

blocks
(
    hex (0 1 2 3 4 5 6 7) ({nx} {ny} {nz}) simpleGrading (1 1 1)
);

boundary
(
    inlet   {{ type patch; faces ((0 4 7 3)); }}
    outlet  {{ type patch; faces ((1 2 6 5)); }}
    ground  {{ type wall;  faces ((0 3 2 1)); }}
    top     {{ type patch; faces ((4 5 6 7)); }}
    sides   {{ type patch; faces ((0 1 5 4) (3 7 6 2)); }}
);
""",
    )


def surface_features(case: Path, stl_name: str) -> None:
    w(
        case / "system/surfaceFeatureExtractDict",
        "dictionary",
        f"""
{stl_name}
{{
    extractionMethod    extractFromSurface;
    includedAngle       170;
    subsetFeatures
    {{
        nonManifoldEdges    no;
        openEdges           yes;
    }}
    writeObj            yes;
}}
""",
    )


def snappy(case: Path, stl_name: str, p: dict) -> None:
    wlo, whi = box_str(p, "wakeBox")
    nlo, nhi = box_str(p, "nearBox")
    glo, ghi = box_str(p, "groundBox")
    glayers = p.get("ground_layers", 0)
    ground_layer_entry = f"        ground {{ nSurfaceLayers {glayers}; }}" if glayers else ""
    w(
        case / "system/snappyHexMeshDict",
        "dictionary",
        f"""
castellatedMesh true;
snap            true;
addLayers       true;

geometry
{{
    {stl_name}
    {{
        type triSurfaceMesh;
        name body;
    }}
    wakeBox
    {{
        type box;
        min ({wlo});
        max ({whi});
    }}
    nearBox
    {{
        type box;
        min ({nlo});
        max ({nhi});
    }}
    groundBox
    {{
        type box;
        min ({glo});
        max ({ghi});
    }}
}}

castellatedMeshControls
{{
    maxLocalCells       600000;
    maxGlobalCells      {p['max_global']};
    minRefinementCells  10;
    maxLoadUnbalance    0.10;
    nCellsBetweenLevels 3;

    features
    (
        {{ file "{stl_name.replace('.stl', '.eMesh')}"; level {p['feature_level']}; }}
    );

    refinementSurfaces
    {{
        body
        {{
            level {p['surface_level']};
            patchInfo {{ type wall; }}
        }}
    }}

    resolveFeatureAngle 30;

    refinementRegions
    {{
        wakeBox   {{ mode inside; levels ((1E15 {p['wake_level']})); }}
        nearBox   {{ mode inside; levels ((1E15 {p['near_level']})); }}
        groundBox {{ mode inside; levels ((1E15 {p['ground_level']})); }}
    }}

    locationInMesh (-1.0 0.0 1.5);
    allowFreeStandingZoneFaces true;
}}

snapControls
{{
    nSmoothPatch    3;
    tolerance       2.0;
    nSolveIter      50;
    nRelaxIter      5;
    nFeatureSnapIter 10;
    implicitFeatureSnap false;
    explicitFeatureSnap true;
    multiRegionFeatureSnap false;
}}

addLayersControls
{{
    relativeSizes false;
    layers
    {{
        body {{ nSurfaceLayers {p['layers']}; }}
{ground_layer_entry}
    }}
    expansionRatio      1.2;
    firstLayerThickness 5e-4;
    minThickness        1e-5;
    nGrow               1;
    featureAngle        150;
    slipFeatureAngle    30;
    nRelaxIter          5;
    nSmoothSurfaceNormals 1;
    nSmoothNormals      3;
    nSmoothThickness    10;
    maxFaceThicknessRatio 0.5;
    maxThicknessToMedialRatio 0.3;
    minMedialAxisAngle  90;
    nBufferCellsNoExtrude 0;
    nLayerIter          50;
}}

meshQualityControls
{{
    #include "meshQualityDict"
    nSmoothScale    4;
    errorReduction  0.75;
}}

writeFlags (scalarLevels layerSets layerFields);
mergeTolerance 1e-6;
""",
    )


def numerics(case: Path, p: dict, nproc: int) -> None:
    w(
        case / "system/decomposeParDict",
        "dictionary",
        f"""
numberOfSubdomains {nproc};
method          scotch;
""",
    )
    w(
        case / "system/controlDict",
        "dictionary",
        f"""
application     simpleFoam;
startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         {p['end_time']};
deltaT          1;
writeControl    timeStep;
writeInterval   {p['write_interval']};
purgeWrite      2;
writeFormat     binary;
writePrecision  8;
writeCompression off;
timeFormat      general;
timePrecision   6;
runTimeModifiable true;

functions
{{
    forceCoeffs1
    {{
        type            forceCoeffs;
        libs            (forces);
        writeControl    timeStep;
        writeInterval   1;
        log             yes;
        patches         (body);
        rho             rhoInf;
        rhoInf          {RHO_INF};
        CofR            (0.5 0 0);
        liftDir         (0 0 1);
        dragDir         (1 0 0);
        pitchAxis       (0 1 0);
        magUInf         {U_INF};
        lRef            {LREF};
        Aref            {AREF};
    }}
    yPlus1
    {{
        type            yPlus;
        libs            (fieldFunctionObjects);
        writeControl    writeTime;
        log             yes;
    }}
    forces1
    {{
        type            forces;
        libs            (forces);
        writeControl    writeTime;
        writeInterval   1;
        log             yes;
        patches         (body);
        rho             rhoInf;
        rhoInf          {RHO_INF};
        CofR            (0.5 0 0);
    }}
    wallShearStress1
    {{
        type            wallShearStress;
        libs            (fieldFunctionObjects);
        writeControl    writeTime;
        log             yes;
    }}
}}
""",
    )
    w(
        case / "system/fvSchemes",
        "dictionary",
        """
ddtSchemes      { default steadyState; }
gradSchemes
{
    default         Gauss linear;
    grad(U)         cellLimited Gauss linear 1;
}
divSchemes
{
    default         none;
    div(phi,U)      bounded Gauss linearUpwind grad(U);
    div(phi,k)      bounded Gauss limitedLinear 1;
    div(phi,omega)  bounded Gauss limitedLinear 1;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes   { default corrected; }
wallDist        { method meshWave; }
""",
    )
    w(
        case / "system/fvSolution",
        "dictionary",
        """
solvers
{
    p
    {
        solver          GAMG;
        tolerance       1e-7;
        relTol          0.01;
        smoother        GaussSeidel;
        nCellsInCoarsestLevel 200;
    }
    "(U|k|omega)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-8;
        relTol          0.1;
    }
    Phi
    {
        $p;
        tolerance       1e-6;
        relTol          0.01;
    }
}

SIMPLE
{
    nNonOrthogonalCorrectors 0;
    consistent      no;
    residualControl
    {
        p               1e-4;
        U               1e-5;
        "(k|omega)"     1e-5;
    }
}

relaxationFactors
{
    fields      { p 0.3; }
    equations   { U 0.7; k 0.7; omega 0.7; }
}
""",
    )


def fields(case: Path, k_inlet: float, omega_inlet: float) -> None:
    K_INLET, OMEGA_INLET = k_inlet, omega_inlet
    w(
        case / "constant/transportProperties",
        "dictionary",
        f"""
transportModel  Newtonian;
nu              {NU};
""",
    )
    w(
        case / "constant/turbulenceProperties",
        "dictionary",
        """
simulationType  RAS;
RAS
{
    RASModel        kOmegaSST;
    turbulence      on;
    printCoeffs     on;
}
""",
    )
    w(
        case / "0/U",
        "volVectorField",
        f"""
dimensions      [0 1 -1 0 0 0 0];
internalField   uniform ({U_INF} 0 0);
boundaryField
{{
    inlet   {{ type fixedValue; value uniform ({U_INF} 0 0); }}
    outlet  {{ type inletOutlet; inletValue uniform (0 0 0); value uniform ({U_INF} 0 0); }}
    ground  {{ type fixedValue; value uniform (0 0 0); }}
    body    {{ type noSlip; }}
    top     {{ type slip; }}
    sides   {{ type slip; }}
}}
""",
    )
    w(
        case / "0/p",
        "volScalarField",
        """
dimensions      [0 2 -2 0 0 0 0];
internalField   uniform 0;
boundaryField
{
    inlet   { type zeroGradient; }
    outlet  { type fixedValue; value uniform 0; }
    ground  { type zeroGradient; }
    body    { type zeroGradient; }
    top     { type slip; }
    sides   { type slip; }
}
""",
    )
    w(
        case / "0/k",
        "volScalarField",
        f"""
dimensions      [0 2 -2 0 0 0 0];
internalField   uniform {K_INLET};
boundaryField
{{
    inlet   {{ type fixedValue; value uniform {K_INLET}; }}
    outlet  {{ type inletOutlet; inletValue uniform {K_INLET}; value uniform {K_INLET}; }}
    ground  {{ type kqRWallFunction; value uniform {K_INLET}; }}
    body    {{ type kqRWallFunction; value uniform {K_INLET}; }}
    top     {{ type slip; }}
    sides   {{ type slip; }}
}}
""",
    )
    w(
        case / "0/omega",
        "volScalarField",
        f"""
dimensions      [0 0 -1 0 0 0 0];
internalField   uniform {OMEGA_INLET};
boundaryField
{{
    inlet   {{ type fixedValue; value uniform {OMEGA_INLET}; }}
    outlet  {{ type inletOutlet; inletValue uniform {OMEGA_INLET}; value uniform {OMEGA_INLET}; }}
    ground  {{ type omegaWallFunction; value uniform {OMEGA_INLET}; }}
    body    {{ type omegaWallFunction; value uniform {OMEGA_INLET}; }}
    top     {{ type slip; }}
    sides   {{ type slip; }}
}}
""",
    )
    w(
        case / "0/nut",
        "volScalarField",
        f"""
dimensions      [0 2 -1 0 0 0 0];
internalField   uniform 0;
boundaryField
{{
    inlet   {{ type calculated; value uniform 0; }}
    outlet  {{ type calculated; value uniform 0; }}
    ground  {{ type nutkWallFunction; value uniform 0; }}
    body    {{ type nutkWallFunction; value uniform 0; }}
    top     {{ type calculated; value uniform 0; }}
    sides   {{ type calculated; value uniform 0; }}
}}
""",
    )


def main() -> int:
    argv = sys.argv[1:]

    def opt(name, default=None, cast=str):
        if name in argv:
            return cast(argv[argv.index(name) + 1])
        return default

    pos = [a for i, a in enumerate(argv) if not a.startswith("--") and (i == 0 or not argv[i - 1].startswith("--"))]
    work = Path(pos[0])
    slant = int(pos[1])
    preset = pos[2]
    nproc = int(pos[3]) if len(pos) > 3 else 12
    p = dict(PRESETS[preset])
    if len(pos) > 4:
        p["end_time"] = int(pos[4])

    p["ground_layers"] = opt("--ground-layers", p.get("ground_layers", 0), int)
    ti = opt("--ti", 0.01, float)
    mixlen = opt("--mixlen", 0.01, float)
    k, omega, ratio = ti_values(ti, mixlen)
    tag = opt("--tag", preset)

    case = work / f"ahmed{slant}_{tag}"
    case.mkdir(parents=True, exist_ok=True)
    stl_name = f"ahmed_{slant}.stl"

    tri = case / "constant/triSurface"
    tri.mkdir(parents=True, exist_ok=True)
    (case / "system").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(work / "geometry" / stl_name, tri / stl_name)
    ref_quality = work / "_ref_motorBike/system/meshQualityDict"
    if not ref_quality.exists():
        raise SystemExit("meshQualityDict reference missing")
    shutil.copyfile(ref_quality, case / "system/meshQualityDict")

    block_mesh(case)
    surface_features(case, stl_name)
    snappy(case, stl_name, p)
    numerics(case, p, nproc)
    fields(case, k, omega)
    print(
        f"case written: {case}\n"
        f"  preset={preset} endTime={p['end_time']} nproc={nproc}\n"
        f"  ground_layers={p['ground_layers']} body_layers={p['layers']}\n"
        f"  TI={ti} mixlen={mixlen} -> k={k:.6g} omega={omega:.6g} nut/nu={ratio:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())