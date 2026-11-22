#!/bin/bash
# Usage (inside container): bash /work/run_case.sh <caseDirName> <nproc> <serial|par>
CASE=$1
NP=$2
MESHMODE=${3:-serial}
cd "/work/$CASE" || exit 2
MPI="mpirun --allow-run-as-root --bind-to none -np $NP"

echo "=== blockMesh ==="
blockMesh > log.blockMesh 2>&1 || { tail -20 log.blockMesh; exit 10; }

echo "=== surfaceFeatureExtract ==="
surfaceFeatureExtract > log.sfe 2>&1 || { tail -20 log.sfe; exit 11; }

if [ "$MESHMODE" = "par" ]; then
  echo "=== decomposePar (mesh) ==="
  decomposePar -force > log.decompMesh 2>&1 || { tail -20 log.decompMesh; exit 12; }
  echo "=== snappyHexMesh (parallel) ==="
  $MPI snappyHexMesh -parallel -overwrite > log.snappy 2>&1 || { tail -30 log.snappy; exit 13; }
  echo "=== reconstructParMesh ==="
  reconstructParMesh -constant > log.reconMesh 2>&1 || { tail -20 log.reconMesh; exit 14; }
  rm -rf processor*
else
  echo "=== snappyHexMesh (serial) ==="
  snappyHexMesh -overwrite > log.snappy 2>&1 || { tail -30 log.snappy; exit 13; }
fi

echo "=== checkMesh ==="
checkMesh -allGeometry -allTopology > log.checkMesh 2>&1
grep -E "  cells:|Mesh OK|Failed [0-9]|Max.*non-orthogonality|Mesh non-orthogonality|skewness" log.checkMesh | head -12

echo "=== potentialFoam ==="
potentialFoam -initialiseUBCs > log.potential 2>&1 || echo "potentialFoam failed (non-fatal, continuing)"

echo "=== decomposePar (solve) ==="
decomposePar -force > log.decomp 2>&1 || { tail -20 log.decomp; exit 15; }

echo "=== simpleFoam ==="
$MPI simpleFoam -parallel > log.simpleFoam 2>&1 || { tail -40 log.simpleFoam; exit 16; }

echo "=== reconstructPar ==="
reconstructPar -latestTime > log.recon 2>&1 || { tail -20 log.recon; exit 17; }

echo "=== yPlus ==="
$MPI simpleFoam -postProcess -func yPlus -latestTime -parallel > log.yPlus 2>&1 || echo "yPlus postProcess failed"
grep -E "y\+ :" log.yPlus | tail -12

echo "=== layer coverage ==="
grep -E "Layer addition|Added [0-9]+ faces|coverage" log.snappy | tail -8

echo "DONE $CASE"