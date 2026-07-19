// ── Merged-cell table engine (colspan + rowspan) ─────────────────────────────
// A table is stored as `cells`: an array of rows, each row an array of cells
// { t: text, cs: colspan, rs: rowspan }. Internally every operation runs on a
// shared-reference occupancy matrix M[r][c] (all positions a merged cell covers
// point to the SAME object), which makes merge/split/insert/delete/move correct
// and uniform on both axes. Legacy cells shaped { t, s } are read as cs = s.

function normCell(c) {
  return { t: c?.t == null ? "" : String(c.t), cs: Math.max(1, c?.cs || c?.s || 1), rs: Math.max(1, c?.rs || 1) };
}

// cells → shared-reference matrix (rectangular, ncols wide)
export function buildMatrix(cells) {
  const rows = (cells || []).map((r) => (r || []).map(normCell));
  const M = [];
  const ensure = (r) => { while (M.length <= r) M.push([]); };
  const taken = (r, c) => M[r] && M[r][c] != null;
  let ncols = 0;
  for (let r = 0; r < rows.length; r++) {
    ensure(r);
    let c = 0;
    for (const cell of rows[r]) {
      ensure(r);
      while (taken(r, c)) c++;
      const obj = { t: cell.t };
      for (let dr = 0; dr < cell.rs; dr++) { ensure(r + dr); for (let dc = 0; dc < cell.cs; dc++) M[r + dr][c + dc] = obj; }
      c += cell.cs;
      ncols = Math.max(ncols, c);
    }
  }
  ncols = Math.max(1, ncols);
  const nrows = Math.max(rows.length, M.length, 1);
  for (let r = 0; r < nrows; r++) { ensure(r); for (let c = 0; c < ncols; c++) if (M[r][c] == null) M[r][c] = { t: "" }; M[r].length = ncols; }
  return M;
}

function boxes(M) {
  const b = new Map();
  for (let r = 0; r < M.length; r++)
    for (let c = 0; c < M[r].length; c++) {
      const o = M[r][c];
      const x = b.get(o);
      if (!x) b.set(o, { r0: r, c0: c, r1: r, c1: c });
      else { x.r0 = Math.min(x.r0, r); x.c0 = Math.min(x.c0, c); x.r1 = Math.max(x.r1, r); x.c1 = Math.max(x.c1, c); }
    }
  return b;
}
function boxOf(M, o) { return boxes(M).get(o); }

export function ncolsOf(M) { return M.length ? M[0].length : 0; }

// matrix → cells (one entry per master, at its top-left)
export function matrixToCells(M) {
  const b = boxes(M);
  const out = [];
  for (let r = 0; r < M.length; r++) {
    const row = [];
    for (let c = 0; c < M[r].length; c++) {
      const x = b.get(M[r][c]);
      if (x.r0 === r && x.c0 === c) row.push({ t: M[r][c].t, cs: x.c1 - x.c0 + 1, rs: x.r1 - x.r0 + 1 });
    }
    out.push(row);
  }
  return out;
}

// matrix → plain per-column text grid (master text at its top-left, else "")
export function matrixToPositional(M) {
  const b = boxes(M);
  return M.map((row, r) => row.map((o, c) => { const x = b.get(o); return x.r0 === r && x.c0 === c ? o.t : ""; }));
}

// matrix → render layout: per row, the master cells starting on that row
export function matrixLayout(M) {
  const b = boxes(M);
  const rows = M.map((row, r) => {
    const out = [];
    row.forEach((o, c) => { const x = b.get(o); if (x.r0 === r && x.c0 === c) out.push({ r, c, t: o.t, cs: x.c1 - x.c0 + 1, rs: x.r1 - x.r0 + 1 }); });
    return out;
  });
  return { nrows: M.length, ncols: ncolsOf(M), rows };
}

// ── operations (mutate matrix) ──
function mergeRight(M, r, c) {
  const o = M[r][c];
  const b = boxOf(M, o);
  if (b.c1 + 1 >= ncolsOf(M)) return false;
  const right = M[b.r0][b.c1 + 1];
  const rb = boxOf(M, right);
  if (rb.r0 !== b.r0 || rb.r1 !== b.r1) return false; // must line up vertically
  for (let rr = rb.r0; rr <= rb.r1; rr++) for (let cc = rb.c0; cc <= rb.c1; cc++) M[rr][cc] = o;
  return true;
}
function mergeDown(M, r, c) {
  const o = M[r][c];
  const b = boxOf(M, o);
  if (b.r1 + 1 >= M.length) return false;
  const down = M[b.r1 + 1][b.c0];
  const db = boxOf(M, down);
  if (db.c0 !== b.c0 || db.c1 !== b.c1) return false; // must line up horizontally
  for (let rr = db.r0; rr <= db.r1; rr++) for (let cc = db.c0; cc <= db.c1; cc++) M[rr][cc] = o;
  return true;
}
function splitAt(M, r, c) {
  const o = M[r][c];
  const b = boxOf(M, o);
  for (let rr = b.r0; rr <= b.r1; rr++) for (let cc = b.c0; cc <= b.c1; cc++) if (!(rr === b.r0 && cc === b.c0)) M[rr][cc] = { t: "" };
  return true;
}
function insertRow(M, idx) {
  const ncols = ncolsOf(M);
  const row = [];
  for (let c = 0; c < ncols; c++) row[c] = (idx > 0 && idx < M.length && M[idx - 1][c] === M[idx][c]) ? M[idx - 1][c] : { t: "" };
  M.splice(idx, 0, row);
}
function insertCol(M, idx) {
  for (let r = 0; r < M.length; r++) M[r].splice(idx, 0, (idx > 0 && idx < M[r].length && M[r][idx - 1] === M[r][idx]) ? M[r][idx - 1] : { t: "" });
}
function moveRow(M, idx, dir) {
  const j = idx + dir;
  if (j < 0 || j >= M.length) return;
  const ncols = ncolsOf(M);
  const split = new Set();
  for (let c = 0; c < ncols; c++) if (M[idx][c] === M[j][c]) split.add(M[idx][c]);
  for (const o of split) { const b = boxOf(M, o); splitAt(M, b.r0, b.c0); }
  [M[idx], M[j]] = [M[j], M[idx]];
}
function moveCol(M, idx, dir) {
  const j = idx + dir;
  if (j < 0 || j >= ncolsOf(M)) return;
  const split = new Set();
  for (let r = 0; r < M.length; r++) if (M[r][idx] === M[r][j]) split.add(M[r][idx]);
  for (const o of split) { const b = boxOf(M, o); splitAt(M, b.r0, b.c0); }
  for (let r = 0; r < M.length; r++) [M[r][idx], M[r][j]] = [M[r][j], M[r][idx]];
}

// ── cells-in / cells-out wrappers used by the editor ──
export function tblSetText(cells, r, c, val) { const M = buildMatrix(cells); if (M[r] && M[r][c]) M[r][c].t = val; return matrixToCells(M); }
export function tblMergeRight(cells, r, c) { const M = buildMatrix(cells); return mergeRight(M, r, c) ? matrixToCells(M) : cells; }
export function tblMergeDown(cells, r, c) { const M = buildMatrix(cells); return mergeDown(M, r, c) ? matrixToCells(M) : cells; }
export function tblSplit(cells, r, c) { const M = buildMatrix(cells); splitAt(M, r, c); return matrixToCells(M); }
export function tblInsertRow(cells, idx, n = 1) { const M = buildMatrix(cells); for (let i = 0; i < Math.max(1, n); i++) insertRow(M, idx); return matrixToCells(M); }
export function tblDeleteRow(cells, idx) { const M = buildMatrix(cells); M.splice(idx, 1); return matrixToCells(M); }
export function tblMoveRow(cells, idx, dir) { const M = buildMatrix(cells); moveRow(M, idx, dir); return matrixToCells(M); }
export function tblInsertCol(cells, idx, n = 1) { const M = buildMatrix(cells); for (let i = 0; i < Math.max(1, n); i++) insertCol(M, idx); return matrixToCells(M); }
export function tblDeleteCol(cells, idx) { const M = buildMatrix(cells); for (let r = 0; r < M.length; r++) M[r].splice(idx, 1); return matrixToCells(M); }
export function tblMoveCol(cells, idx, dir) { const M = buildMatrix(cells); moveCol(M, idx, dir); return matrixToCells(M); }

// helpers for converters / rendering
export function cellsLayout(cells) { return matrixLayout(buildMatrix(cells)); }
export function cellsToPositional(cells) { return matrixToPositional(buildMatrix(cells)); }
export function cellsNcols(cells) { return ncolsOf(buildMatrix(cells)); }
export { normCell };
