/* board.jsx — chess board rendering, position engine, eval bar */
const PIECE = { k:'♚', q:'♛', r:'♜', b:'♝', n:'♞', p:'♟' };

const START = (() => {
  // board[rank][file], rank 0 = rank1. piece = {t, c} or null
  const b = Array.from({length:8}, () => Array(8).fill(null));
  const back = ['r','n','b','q','k','b','n','r'];
  for (let f=0; f<8; f++) {
    b[0][f] = { t: back[f], c: 'w' };
    b[1][f] = { t: 'p', c: 'w' };
    b[6][f] = { t: 'p', c: 'b' };
    b[7][f] = { t: back[f], c: 'b' };
  }
  return b;
})();

function sq(s) { return { f: s.charCodeAt(0) - 97, r: s.charCodeAt(1) - 49 }; }
function clone(b) { return b.map(row => row.map(c => c ? { ...c } : null)); }

function applyMove(board, m) {
  const b = clone(board);
  const from = sq(m.from), to = sq(m.to);
  const pc = b[from.r][from.f];
  if (!pc) return b;
  // castling: king moves two files
  if (pc.t === 'k' && Math.abs(to.f - from.f) === 2) {
    const rank = from.r;
    if (to.f === 6) { b[rank][5] = b[rank][7]; b[rank][7] = null; }      // kingside
    else if (to.f === 2) { b[rank][3] = b[rank][0]; b[rank][0] = null; } // queenside
  }
  b[to.r][to.f] = m.promo ? { t: m.promo, c: pc.c } : pc;
  b[from.r][from.f] = null;
  return b;
}

// positions[i] = board AFTER moves[0..i-1]; positions[0] = start
function buildPositions(moves) {
  const out = [START];
  let cur = START;
  for (const m of moves) { cur = applyMove(cur, m); out.push(cur); }
  return out;
}

function Board({ position, lastMove, flip, coords = true }) {
  const ranks = flip ? [...Array(8).keys()] : [...Array(8).keys()].reverse();
  const files = flip ? [...Array(8).keys()].reverse() : [...Array(8).keys()];
  const hl = lastMove ? [sq(lastMove.from), sq(lastMove.to)] : [];
  const isHl = (r, f) => hl.some(s => s.r === r && s.f === f);
  return (
    <div className="board">
      <div className="board-grid">
        {ranks.map(r => files.map(f => {
          const dark = (r + f) % 2 === 0;
          const pc = position[r][f];
          return (
            <div key={r + '-' + f} className={'sq ' + (dark ? 'dark' : 'light') + (isHl(r, f) ? ' hl' : '')}>
              {coords && f === files[0] && <span className="coord rank">{r + 1}</span>}
              {coords && r === ranks[ranks.length - 1] && <span className="coord file">{String.fromCharCode(97 + f)}</span>}
              {pc && <img className="pc" alt="" draggable="false" src={(window.__resources && window.__resources['piece_' + pc.c + pc.t.toUpperCase()]) || ('LLM Chess Arena/pieces/' + pc.c + pc.t.toUpperCase() + '.svg')} />}
            </div>
          );
        }))}
      </div>
    </div>
  );
}

// cp from white POV -> white share of bar (0..1), clamped
function evalShare(cp) {
  const x = Math.max(-800, Math.min(800, cp));
  return 0.5 + (x / 800) * 0.5;
}

function EvalBar({ cp }) {
  return (
    <div className="evalbar" title={(cp >= 0 ? '+' : '') + (cp / 100).toFixed(1)}>
      <div className="tick"></div>
      <div className="white" style={{ height: (evalShare(cp) * 100).toFixed(1) + '%' }}></div>
    </div>
  );
}

Object.assign(window, { PIECE, START, applyMove, buildPositions, Board, EvalBar, evalShare });
