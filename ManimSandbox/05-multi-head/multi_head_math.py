"""Independent, standard-library-only math for the E6.5 two-head example.

This module is the source of truth for the scene's matrices and the
verification script. It computes Q/K/V, scores, softmax weights, per-head
contexts, concatenation and output projection from the matrices below. It
does not contain pre-filled expected numeric outputs.
"""

from __future__ import annotations

import math

TOKENS = ["The", "cat", "sat", "on"]
QUERY_INDEX = 1

X = [
    [1.0, 0.0, 1.0, 0.0],
    [0.0, 1.0, 0.0, 1.0],
    [1.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 1.0],
]

W_Q1 = [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0], [0.0, 1.0]]
W_K1 = [[0.0, 1.0], [1.0, 0.0], [0.0, 1.0], [1.0, 0.0]]
W_V1 = [[0.5, 0.0], [0.0, 0.5], [0.5, 0.0], [0.0, 0.5]]

W_Q2 = [[0.0, 0.0], [1.0, 0.0], [0.0, 0.0], [1.0, 0.0]]
W_K2 = [[1.0, 0.0], [1.0, 0.0], [0.0, 0.0], [0.0, 0.0]]
W_V2 = [[1.0, 0.0], [0.0, 1.0], [1.0, 0.0], [0.0, 0.0]]

W_O = [
    [1.0, 0.0, 0.25, 0.0],
    [0.0, 1.0, 0.0, 0.5],
    [0.25, 0.0, 1.0, 0.0],
    [0.0, 0.5, 0.0, 1.0],
]


def matmul(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    if not left or not right:
        raise ValueError("matmul requires non-empty matrices")
    if len(left[0]) != len(right):
        raise ValueError(
            f"matmul shape mismatch: {len(left)}x{len(left[0])} times "
            f"{len(right)}x{len(right[0])}"
        )
    columns = len(right[0])
    return [
        [
            sum(left[row][k] * right[k][col] for k in range(len(right)))
            for col in range(columns)
        ]
        for row in range(len(left))
    ]


def transpose(matrix: list[list[float]]) -> list[list[float]]:
    if not matrix:
        raise ValueError("transpose requires a non-empty matrix")
    return [list(column) for column in zip(*matrix)]


def softmax(row: list[float]) -> list[float]:
    if not row:
        raise ValueError("softmax requires a non-empty row")
    peak = max(row)
    exps = [math.exp(value - peak) for value in row]
    total = sum(exps)
    return [value / total for value in exps]


def attention(
    x: list[list[float]],
    w_q: list[list[float]],
    w_k: list[list[float]],
    w_v: list[list[float]],
) -> dict:
    q = matmul(x, w_q)
    k = matmul(x, w_k)
    v = matmul(x, w_v)
    d_k = len(w_q[0])
    scale = math.sqrt(d_k)
    scores = [
        [
            sum(q[row][i] * k[col][i] for i in range(d_k)) / scale
            for col in range(len(k))
        ]
        for row in range(len(q))
    ]
    alpha = [softmax(row) for row in scores]
    context = matmul(alpha, v)
    return {
        "q": q,
        "k": k,
        "v": v,
        "d_k": d_k,
        "scores": scores,
        "alpha": alpha,
        "context": context,
    }


def concat_heads(heads: list[dict]) -> list[list[float]]:
    token_count = len(heads[0]["context"])
    return [
        [value for head in heads for value in head["context"][row]]
        for row in range(token_count)
    ]


def _check(check_id: str, ok: bool, detail: str) -> dict:
    return {"id": check_id, "ok": ok, "detail": detail}


def _shape(matrix: list[list[float]]) -> tuple[int, int]:
    return len(matrix), len(matrix[0])


def compute() -> dict:
    head1 = attention(X, W_Q1, W_K1, W_V1)
    head2 = attention(X, W_Q2, W_K2, W_V2)
    concat = concat_heads([head1, head2])
    final = matmul(concat, W_O)

    checks: list[dict] = []
    checks.append(_check("x_shape", _shape(X) == (4, 4), f"X shape={_shape(X)}"))
    checks.append(
        _check("q1_shape", _shape(head1["q"]) == (4, 2), f"Q1 shape={_shape(head1['q'])}")
    )
    checks.append(
        _check("k1_shape", _shape(head1["k"]) == (4, 2), f"K1 shape={_shape(head1['k'])}")
    )
    checks.append(
        _check("v1_shape", _shape(head1["v"]) == (4, 2), f"V1 shape={_shape(head1['v'])}")
    )
    checks.append(
        _check(
            "scores1_shape",
            _shape(head1["scores"]) == (4, 4),
            f"scores1 shape={_shape(head1['scores'])}",
        )
    )
    checks.append(
        _check(
            "alpha1_shape",
            _shape(head1["alpha"]) == (4, 4),
            f"alpha1 shape={_shape(head1['alpha'])}",
        )
    )
    checks.append(
        _check(
            "context1_shape",
            _shape(head1["context"]) == (4, 2),
            f"context1 shape={_shape(head1['context'])}",
        )
    )
    checks.append(
        _check("q2_shape", _shape(head2["q"]) == (4, 2), f"Q2 shape={_shape(head2['q'])}")
    )
    checks.append(
        _check("k2_shape", _shape(head2["k"]) == (4, 2), f"K2 shape={_shape(head2['k'])}")
    )
    checks.append(
        _check("v2_shape", _shape(head2["v"]) == (4, 2), f"V2 shape={_shape(head2['v'])}")
    )
    checks.append(
        _check(
            "scores2_shape",
            _shape(head2["scores"]) == (4, 4),
            f"scores2 shape={_shape(head2['scores'])}",
        )
    )
    checks.append(
        _check(
            "alpha2_shape",
            _shape(head2["alpha"]) == (4, 4),
            f"alpha2 shape={_shape(head2['alpha'])}",
        )
    )
    checks.append(
        _check(
            "context2_shape",
            _shape(head2["context"]) == (4, 2),
            f"context2 shape={_shape(head2['context'])}",
        )
    )
    checks.append(
        _check("concat_shape", _shape(concat) == (4, 4), f"concat shape={_shape(concat)}")
    )
    checks.append(
        _check("final_shape", _shape(final) == (4, 4), f"final shape={_shape(final)}")
    )
    checks.append(
        _check("d_model_relation", 2 * 2 == 4, "h * d_k = 2 * 2 = d_model = 4")
    )
    checks.append(
        _check("concat_width", 2 + 2 == 4, "concat width = 2 + 2 = 4")
    )

    for name, head in (("head1", head1), ("head2", head2)):
        for row, row_values in enumerate(head["alpha"]):
            total = sum(row_values)
            checks.append(
                _check(
                    f"{name}_alpha_row_{row}_sum",
                    abs(total - 1.0) <= 1e-9,
                    f"sum={total:.12f}",
                )
            )

    head_delta = max(
        abs(a - b)
        for row_a, row_b in zip(head1["alpha"], head2["alpha"])
        for a, b in zip(row_a, row_b)
    )
    checks.append(
        _check("heads_differ", head_delta > 0.4, f"max alpha delta={head_delta:.6f}")
    )

    head1_query = head1["alpha"][QUERY_INDEX]
    head2_query = head2["alpha"][QUERY_INDEX]
    head1_argmax = max(range(len(head1_query)), key=head1_query.__getitem__)
    head2_argmax = max(range(len(head2_query)), key=head2_query.__getitem__)
    checks.append(
        _check(
            "head1_query_focus",
            head1_argmax == 0,
            f"{TOKENS[QUERY_INDEX]} focuses {TOKENS[head1_argmax]}",
        )
    )
    checks.append(
        _check(
            "head2_query_focus",
            head2_argmax == 2,
            f"{TOKENS[QUERY_INDEX]} focuses {TOKENS[head2_argmax]}",
        )
    )

    concat_layout_ok = all(
        concat[row][:2] == head1["context"][row]
        and concat[row][2:] == head2["context"][row]
        for row in range(len(concat))
    )
    checks.append(
        _check("concat_layout", concat_layout_ok, "concat = [head1 | head2] by columns")
    )
    mix_delta = max(
        abs(a - b) for row_a, row_b in zip(final, concat) for a, b in zip(row_a, row_b)
    )
    checks.append(
        _check("output_projection_mixes", mix_delta > 1e-6, f"max delta={mix_delta:.6f}")
    )

    return {
        "schema_version": 1,
        "kind": "e6_5_math_report",
        "lesson": "e6.5-multi-head",
        "tokens": TOKENS,
        "query_token": TOKENS[QUERY_INDEX],
        "dimensions": {
            "tokens": len(X),
            "d_model": len(X[0]),
            "heads": 2,
            "d_k": head1["d_k"],
            "d_v": len(W_V1[0]),
            "concat_width": len(concat[0]),
        },
        "matrices": {
            "X": X,
            "W_Q1": W_Q1,
            "W_K1": W_K1,
            "W_V1": W_V1,
            "W_Q2": W_Q2,
            "W_K2": W_K2,
            "W_V2": W_V2,
            "W_O": W_O,
        },
        "heads": [
            {"name": "head1", **head1},
            {"name": "head2", **head2},
        ],
        "concat": concat,
        "final": final,
        "checks": checks,
        "all_ok": all(item["ok"] for item in checks),
    }
