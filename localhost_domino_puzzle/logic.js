class Domino {
  constructor(left, right, id) {
    this.id = id;
    this.left = left;
    this.right = right;
    this.orientation = 'HORIZONTAL';
    this.inPool = true;
    this.dragging = false;
    
    // Pixel coordinates for dragging/rendering
    this.x = 0;
    this.y = 0;
    
    // Origin in pool
    this.poolX = 0;
    this.poolY = 0;
  }
  
  rotate() {
    if (this.orientation === 'VERTICAL') {
      this.orientation = 'HORIZONTAL';
      // Swap left and right like Pygame logic does
      const temp = this.left;
      this.left = this.right;
      this.right = temp;
    } else {
      this.orientation = 'VERTICAL';
    }
  }

  valueAt(halfIdx) {
    return halfIdx === 0 ? this.left : this.right;
  }
}

class Board {
  constructor(size = 16) {
    this.size = size;
    // grid[r][c] = -1 -> empty, else pip value
    this.grid = Array.from({ length: size }, () => Array(size).fill(-1));
    // stringified coordinate to { domino, halfIdx }
    this.map = new Map();
    this.isValid = true;
    this.numDom = 0;
  }

  // Gets the cell bounds for a domino placed at row, col
  _cellsFor(d, row, col) {
    return d.orientation === 'HORIZONTAL' 
      ? [[row, col], [row, col + 1]] 
      : [[row, col], [row + 1, col]];
  }

  _boundsOk(cells) {
    return cells.every(([r, c]) => r >= 0 && r < this.size && c >= 0 && c < this.size);
  }

  _free(cells) {
    return cells.every(([r, c]) => this.grid[r][c] === -1);
  }

  *_neighbors(r, c) {
    const dirs = [[-1, 0], [1, 0], [0, -1], [0, 1]];
    for (const [dr, dc] of dirs) {
      const nr = r + dr, nc = c + dc;
      if (nr >= 0 && nr < this.size && nc >= 0 && nc < this.size) {
        yield [nr, nc];
      }
    }
  }

  _adjacencyOk(d, row, col) {
    const cells = this._cellsFor(d, row, col);
    for (let idx = 0; idx < cells.length; idx++) {
      const [r, c] = cells[idx];
      const v = d.valueAt(idx);
      const other = cells[1 - idx];
      
      for (const [nr, nc] of this._neighbors(r, c)) {
        if (nr === other[0] && nc === other[1]) continue;
        const nbVal = this.grid[nr][nc];
        if (nbVal !== -1 && nbVal !== v) {
          return false;
        }
      }
    }
    return true;
  }

  canPlace(d, row, col) {
    const cells = this._cellsFor(d, row, col);
    return this._boundsOk(cells) && this._free(cells) && this._adjacencyOk(d, row, col);
  }

  place(d, row, col) {
    if (!this.canPlace(d, row, col)) return false;
    
    const cells = this._cellsFor(d, row, col);
    for (let idx = 0; idx < cells.length; idx++) {
      const [r, c] = cells[idx];
      this.grid[r][c] = d.valueAt(idx);
      this.map.set(`${r},${c}`, { domino: d, idx });
    }
    
    d.dragging = false;
    d.inPool = false;
    this.numDom++;
    this.updateValid();
    return true;
  }

  lift(d) {
    // Remove from map and grid
    for (const [coordStr, data] of this.map.entries()) {
      if (data.domino === d) {
        const [r, c] = coordStr.split(',').map(Number);
        this.grid[r][c] = -1;
        this.map.delete(coordStr);
      }
    }
    this.numDom--;
    this.updateValid();
  }

  validPosition() {
    const occ = [];
    for (let r = 0; r < this.size; r++) {
      for (let c = 0; c < this.size; c++) {
        if (this.grid[r][c] !== -1) occ.push([r, c]);
      }
    }
    if (occ.length === 0) return true;

    // 1. Global Connectivity (BFS)
    const seen = new Set();
    const q = [occ[0]];
    seen.add(`${occ[0][0]},${occ[0][1]}`);
    
    while (q.length > 0) {
      const [r, c] = q.shift();
      for (const [nr, nc] of this._neighbors(r, c)) {
        if (this.grid[nr][nc] !== -1 && !seen.has(`${nr},${nc}`)) {
          seen.add(`${nr},${nc}`);
          q.push([nr, nc]);
        }
      }
    }
    if (seen.size !== occ.length) return false;

    // 2. Per-value connectivity
    const values = [...new Set(occ.map(([r, c]) => this.grid[r][c]))];
    
    for (const v of values) {
      const cellsV = occ.filter(([r, c]) => this.grid[r][c] === v);
      if (cellsV.length <= 1) continue;

      const seenV = new Set();
      const qV = [cellsV[0]];
      seenV.add(`${cellsV[0][0]},${cellsV[0][1]}`);
      
      while (qV.length > 0) {
        const [r, c] = qV.shift();
        for (const [nr, nc] of this._neighbors(r, c)) {
          if (this.grid[nr][nc] === v && !seenV.has(`${nr},${nc}`)) {
            seenV.add(`${nr},${nc}`);
            qV.push([nr, nc]);
          }
        }
      }
      if (seenV.size !== cellsV.length) return false;
    }

    return true;
  }

  updateValid() {
    this.isValid = this.validPosition();
  }
}
