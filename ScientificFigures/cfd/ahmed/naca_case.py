"""NACA 0012 2D incompressible case, adapted from the v2512 rhoSimpleFoam tutorial.

Reuses the tutorial's body-fitted C-grid blockMeshDict (vertices projected onto
NACA0012.obj) and its extrudeMeshDict; replaces the compressible solver setup with
simpleFoam + kOmegaSST at Re_c = 1e6 and alpha = 5 deg.

The 2D plane is x-z; extrusion is along y. Angle of attack is imposed by rotating
the freestream vector, not the geometry.

Usage: python naca_case.py <workroot> [--alpha 5] [--ref <refcase>] [--tag naca0012]
"""

import re
import shutil
import sys
from pathlib import Path

NU = 1.5e-5
CHORD = 1.0
RE = 1.0e6
U_INF = RE * NU / CHORD  # 15 m/s
RHO_INF = 1.225
CMU = 0.09
TI = 0.002
MIXLEN = 1.0e-3

HEADER = """FoamFile
{
    version     2.0;
    format      ascii;
    class       %s;
    object      %s;
}
"""

# finer than the tutorial default: first cell ~2.4e-5 m -> y+ < 1 (wall-resolved)
DOMAIN = {
    "zCells": 140,
    "xUCells": 40,
    "xMCells": 120,
    "xDCells": 60,
    "zGrading": 5000,
    "xUGrading": 5,
    "leadGrading": 0.2,
    "xDGrading": 10,
}


def w(path: Path, cls: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER % (cls, path.name) + body, encoding="utf-8", newline="\n")


def patch_domain(text: str) -> str:
    for key, val in DOMAIN.items():
        text, n = re.subn(rf"(\b{key}\s+)[-\d.eE+]+(\s*;)", rf"\g<1>{val}\g<2>", text)
        if n != 1:
            raise SystemExit(f"blockMeshDict: expected exactly one '{key}', found {n}")
    return text


def main() -> int:
    argv = sys.argv[1:]

    def opt(name, default, cast=str):
        return cast(argv[argv.index(name) + 1]) if name in argv else default

    work = Path(argv[0])
    alpha = opt("--alpha", 5.0, float)
    ref = Path(opt("--ref", str(work / "_ref_naca0012")))
    tag = opt("--tag", "naca0012")
    case = work / tag
    case.mkdir(parents=True, exist_ok=True)

    import math

    a = math.radians(alpha)
    ux, uz = U_INF * math.cos(a), U_INF * math.sin(a)
    k = 1.5 * (U_INF * TI) ** 2
    omega = k**0.5 / (CMU**0.25 * MIXLEN)

    (case / "constant/geometry").mkdir(parents=True, exist_ok=True)
    (case / "system").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ref / "system/blockMeshDict", case / "system/blockMeshDict")
    bm = case / "system/blockMeshDict"
    bm.write_text(patch_domain(bm.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    shutil.copyfile(ref / "system/extrudeMeshDict", case / "system/extrudeMeshDict")
    obj = Path("/work/_ref_naca0012/constant/geometry/NACA0012.obj.gz")
    if not obj.exists():
        # populated inside the container by run_naca.sh
        pass

    w(case / "constant/transportProperties", "dictionary",
      f"transportModel  Newtonian;\nnu              {NU};\n")
    w(case / "constant/turbulenceProperties", "dictionary",
      "simulationType  RAS;\nRAS\n{\n    RASModel        kOmegaSST;\n"
      "    turbulence      on;\n    printCoeffs     on;\n}\n")

    w(case / "system/controlDict", "dictionary", f"""
application     simpleFoam;
startFrom       latestTime;
startTime       0;
stopAt          endTime;
endTime         2000;
deltaT          1;
writeControl    timeStep;
writeInterval   500;
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
        patches         (aerofoil);
        rho             rhoInf;
        rhoInf          {RHO_INF};
        CofR            (0.25 0 0);
        liftDir         ({-math.sin(a)} 0 {math.cos(a)});
        dragDir         ({math.cos(a)} 0 {math.sin(a)});
        pitchAxis       (0 1 0);
        magUInf         {U_INF};
        lRef            {CHORD};
        Aref            {CHORD};
    }}
    yPlus1
    {{
        type            yPlus;
        libs            (fieldFunctionObjects);
        writeControl    writeTime;
        log             yes;
    }}
}}
""")

    w(case / "system/fvSchemes", "dictionary", """
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
""")

    w(case / "system/fvSolution", "dictionary", """
solvers
{
    p
    {
        solver          GAMG;
        tolerance       1e-8;
        relTol          0.01;
        smoother        GaussSeidel;
        nCellsInCoarsestLevel 100;
    }
    "(U|k|omega)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-9;
        relTol          0.1;
    }
    Phi
    {
        $p;
        tolerance       1e-7;
        relTol          0.01;
    }
}

SIMPLE
{
    nNonOrthogonalCorrectors 0;
    consistent      yes;
    residualControl
    {
        p               1e-5;
        U               1e-6;
        "(k|omega)"     1e-6;
    }
}

relaxationFactors
{
    fields      { p 0.3; }
    equations   { U 0.7; k 0.7; omega 0.7; }
}
""")

    w(case / "system/decomposeParDict", "dictionary",
      "numberOfSubdomains 4;\nmethod          scotch;\n")

    w(case / "0/U", "volVectorField", f"""
dimensions      [0 1 -1 0 0 0 0];
internalField   uniform ({ux} 0 {uz});
boundaryField
{{
    freestream
    {{
        type            freestreamVelocity;
        freestreamValue uniform ({ux} 0 {uz});
        value           uniform ({ux} 0 {uz});
    }}
    aerofoil        {{ type noSlip; }}
    #includeEtc "caseDicts/setConstraintTypes"
}}
""")

    w(case / "0/p", "volScalarField", f"""
dimensions      [0 2 -2 0 0 0 0];
internalField   uniform 0;
boundaryField
{{
    freestream
    {{
        type            freestreamPressure;
        freestreamValue uniform 0;
        value           uniform 0;
    }}
    aerofoil        {{ type zeroGradient; }}
    #includeEtc "caseDicts/setConstraintTypes"
}}
""")

    # wall-resolved (y+ < 1): Spalding nut is valid across the whole y+ range,
    # kLowReWallFunction drives k to zero at the wall, omegaWallFunction blends.
    w(case / "0/k", "volScalarField", f"""
dimensions      [0 2 -2 0 0 0 0];
internalField   uniform {k};
boundaryField
{{
    freestream
    {{
        type            freestream;
        freestreamValue uniform {k};
        value           uniform {k};
    }}
    aerofoil        {{ type kLowReWallFunction; value uniform 0; }}
    #includeEtc "caseDicts/setConstraintTypes"
}}
""")

    w(case / "0/omega", "volScalarField", f"""
dimensions      [0 0 -1 0 0 0 0];
internalField   uniform {omega};
boundaryField
{{
    freestream
    {{
        type            freestream;
        freestreamValue uniform {omega};
        value           uniform {omega};
    }}
    aerofoil        {{ type omegaWallFunction; value uniform {omega}; }}
    #includeEtc "caseDicts/setConstraintTypes"
}}
""")

    w(case / "0/nut", "volScalarField", f"""
dimensions      [0 2 -1 0 0 0 0];
internalField   uniform 0;
boundaryField
{{
    freestream      {{ type calculated; value uniform 0; }}
    aerofoil        {{ type nutUSpaldingWallFunction; value uniform 0; }}
    #includeEtc "caseDicts/setConstraintTypes"
}}
""")

    print(
        f"case written: {case}\n"
        f"  alpha={alpha} deg  U=({ux:.6f} 0 {uz:.6f})  |U|={U_INF} m/s\n"
        f"  Re_c={U_INF * CHORD / NU:.4g}  chord={CHORD} m  nu={NU}\n"
        f"  TI={TI} mixlen={MIXLEN} -> k={k:.6g} omega={omega:.6g} nut/nu={(k / omega) / NU:.3f}\n"
        f"  grid: zCells={DOMAIN['zCells']} zGrading={DOMAIN['zGrading']} "
        f"x=({DOMAIN['xUCells']}+{DOMAIN['xMCells']}+{DOMAIN['xDCells']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())