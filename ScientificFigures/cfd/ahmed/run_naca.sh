#!/bin/bash
# Usage (inside container): bash /work/run_naca.sh <caseDirName>
# blockMesh already yields a 1-cell-thick mesh with empty front/back, so the
# tutorial's extrudeMesh step is not needed here.
CASE=$1
cd "/work/$CASE" || exit 2

mkdir -p constant/geometry
cp -f "$FOAM_TUTORIALS/resources/geometry/NACA0012.obj.gz" constant/geometry/ || exit 3

echo "=== blockMesh ==="
blockMesh > log.blockMesh 2>&1 || { tail -25 log.blockMesh; exit 10; }
grep -E "  cells:|  faces:" log.blockMesh | head -3

echo "=== checkMesh ==="
checkMesh -allGeometry -allTopology > log.checkMesh 2>&1
grep -E "  cells:|Mesh OK|Failed [0-9]|non-orthogonality Max|Max skewness|Mesh has .* geometric" log.checkMesh | head -8

echo "=== potentialFoam ==="
potentialFoam -initialiseUBCs > log.potential 2>&1 || echo "potentialFoam failed (non-fatal)"

echo "=== simpleFoam (serial) ==="
simpleFoam > log.simpleFoam 2>&1 || { tail -40 log.simpleFoam; exit 16; }
tail -3 log.simpleFoam

echo "=== yPlus ==="
simpleFoam -postProcess -func yPlus -latestTime > log.yPlus 2>&1 || echo "yPlus failed"
grep -E "y\+ :" log.yPlus | tail -4

echo "DONE $CASE"