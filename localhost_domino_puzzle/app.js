// app.js

const BOARD_SZ = 16;
const DOMINO_NUM = 14;

let board = new Board(BOARD_SZ);
let dominoes = [];
let draggingDomino = null;
let dragOffsetX = 0;
let dragOffsetY = 0;
let isDragged = false; // to distinguish click vs drag

// DOM elements
const elBoard = document.getElementById('board');
const elPool = document.getElementById('domino-pool');
const elIndicator = document.getElementById('status-indicator');
const elBtnNew = document.getElementById('btn-new');
const elBtnReset = document.getElementById('btn-reset');

// Initialize grid cells visually
function initGridDOM() {
  elBoard.innerHTML = '';
  for (let r = 0; r < BOARD_SZ; r++) {
    for (let c = 0; c < BOARD_SZ; c++) {
      const cell = document.createElement('div');
      cell.classList.add('cell');
      // For debugging or mapping
      cell.dataset.row = r;
      cell.dataset.col = c;
      elBoard.appendChild(cell);
    }
  }
}

// Generate domino DOM elements
function renderDomino(d) {
  const el = document.createElement('div');
  el.classList.add('domino', d.orientation.toLowerCase());
  el.id = `domino-${d.id}`;
  
  const h1 = document.createElement('div');
  h1.classList.add('half');
  h1.innerHTML = `<span class="pip-${d.left}">${d.left}</span>`;
  
  const h2 = document.createElement('div');
  h2.classList.add('half');
  h2.innerHTML = `<span class="pip-${d.right}">${d.right}</span>`;
  
  el.appendChild(h1);
  el.appendChild(h2);
  
  // Interaction
  el.addEventListener('pointerdown', (e) => onPointerDown(e, d, el));
  
  return el;
}

// Layout dominoes in the pool visually
function layoutSidebar() {
  elPool.innerHTML = `<p class="pool-hint">Drag dominoes to the board.<br>Click or press 'R' to rotate.</p>`;
  for (let i = 0; i < dominoes.length; i++) {
    const d = dominoes[i];
    d.inPool = true;
    d.orientation = 'HORIZONTAL';
    const el = renderDomino(d);
    
    // Position relatively in pool
    el.style.position = 'relative';
    el.style.left = '0px';
    el.style.top = '0px';
    el.style.margin = '10px 0';
    
    elPool.appendChild(el);
    d.el = el;
  }
}

// Main puzzle loading
function loadPuzzle() {
  board = new Board(BOARD_SZ);
  
  // Pick random from solvablePuzzles (assuming solvablePuzzles is globally available)
  const puzList = window.solvablePuzzles || solvablePuzzles;
  const idx = Math.floor(Math.random() * puzList.length);
  const puzzlePairs = puzList[idx];
  
  dominoes = puzzlePairs.map((pair, i) => new Domino(pair[0], pair[1], i));
  
  layoutSidebar();
  updateIndicator();
}

function updateIndicator() {
  elIndicator.className = 'indicator'; // reset
  if (board.isValid) {
    if (board.numDom === DOMINO_NUM) {
      elIndicator.classList.add('valid-complete');
      elIndicator.innerText = 'Solved / Complete';
    } else {
      elIndicator.classList.add('valid-incomplete');
      elIndicator.innerText = 'Incomplete';
    }
  } else {
    elIndicator.classList.add('invalid');
    elIndicator.innerText = 'Invalid';
  }
}

// View Helper - update styles based on domino state
function updateDominoOrientationDOM(d) {
  d.el.className = `domino ${d.dragging ? 'dragging' : ''} ${d.orientation.toLowerCase()}`;
  // Swap the visual halves
  const spans = d.el.querySelectorAll('span');
  if (spans.length === 2) {
    spans[0].className = `pip-${d.valueAt(0)}`;
    spans[0].innerText = d.valueAt(0);
    spans[1].className = `pip-${d.valueAt(1)}`;
    spans[1].innerText = d.valueAt(1);
  }
}

// Interaction
function onPointerDown(e, d, el) {
  if (e.button !== 0 && e.pointerType === 'mouse') return; // only left click
  
  // If placed, lift it
  if (!d.inPool) {
    board.lift(d);
    updateIndicator();
  }
  
  // We need to measure offset for smooth drag
  const rect = el.getBoundingClientRect();
  dragOffsetX = e.clientX - rect.left;
  dragOffsetY = e.clientY - rect.top;
  
  d.dragging = true;
  draggingDomino = d;
  isDragged = false;
  
  // Move to body level for absolute positioning
  document.body.appendChild(el);
  el.style.position = 'absolute';
  el.style.left = e.clientX - dragOffsetX + 'px';
  el.style.top = e.clientY - dragOffsetY + 'px';
  el.style.zIndex = '1000';
  
  updateDominoOrientationDOM(d);
  
  el.setPointerCapture(e.pointerId);
}

document.addEventListener('pointermove', (e) => {
  if (!draggingDomino) return;
  
  isDragged = true;
  const el = draggingDomino.el;
  el.style.left = e.clientX - dragOffsetX + 'px';
  el.style.top = e.clientY - dragOffsetY + 'px';
});

document.addEventListener('pointerup', (e) => {
  if (!draggingDomino) return;
  
  const d = draggingDomino;
  const el = d.el;
  
  // No click-to-rotate anymore, use 'R' key
  
  el.releasePointerCapture(e.pointerId);
  d.dragging = false;
  draggingDomino = null;
  updateDominoOrientationDOM(d); // remove dragging visuals
  
  // Check drop over board
  const boardRect = elBoard.getBoundingClientRect();
  const dRect = el.getBoundingClientRect();
  
  // Use the center of the first half as the drop coordinate check
  const cellW = boardRect.width / BOARD_SZ;
  let anchorX, anchorY;
  
  if (d.orientation === 'HORIZONTAL') {
    anchorX = dRect.left + (dRect.width / 4);
    anchorY = dRect.top + (dRect.height / 2);
  } else {
    anchorX = dRect.left + (dRect.width / 2);
    anchorY = dRect.top + (dRect.height / 4);
  }

  // Are we over the board?
  if (
    anchorX >= boardRect.left && anchorX <= boardRect.right &&
    anchorY >= boardRect.top && anchorY <= boardRect.bottom
  ) {
    const col = Math.floor((anchorX - boardRect.left) / cellW);
    const row = Math.floor((anchorY - boardRect.top) / cellW);
    
    if (board.place(d, row, col)) {
      // Snap to grid
      el.style.position = 'absolute';
      el.style.left = (boardRect.left + col * cellW) + 'px';
      el.style.top = (boardRect.top + row * cellW) + 'px';
      el.style.margin = '0';
      // It stays in body, but absolute positioned exactly over the board
    } else {
      returnToPool(d);
    }
  } else {
    returnToPool(d);
  }
  
  updateIndicator();
});

function returnToPool(d) {
  d.inPool = true;
  d.orientation = 'HORIZONTAL';
  d.dragging = false;
  
  const el = d.el;
  elPool.appendChild(el);
  
  el.style.position = 'relative';
  el.style.left = '0px';
  el.style.top = '0px';
  el.style.margin = '10px 0';
  el.style.zIndex = '';
  
  updateDominoOrientationDOM(d);
}

// Window resize -> update grid snap positions
window.addEventListener('resize', () => {
  const boardRect = elBoard.getBoundingClientRect();
  const cellW = boardRect.width / BOARD_SZ;
  
  // reposition all dominos that are placed on the board
  for (const [coordStr, data] of board.map.entries()) {
    const d = data.domino;
    // We only need to process each domino once, but map stores both halves.
    // So just reposition when idx == 0
    if (data.idx === 0) {
      const [r, c] = coordStr.split(',').map(Number);
      const el = d.el;
      el.style.left = (boardRect.left + c * cellW) + 'px';
      el.style.top = (boardRect.top + r * cellW) + 'px';
    }
  }
});

// Key bindings
window.addEventListener('keydown', (e) => {
  if ((e.code === 'KeyR' || e.key === 'r') && draggingDomino) {
    draggingDomino.rotate();
    updateDominoOrientationDOM(draggingDomino);
    
    // visually adjust center point around the cursor
    const rect = draggingDomino.el.getBoundingClientRect();
    // we want the mouse to stay roughly in the same spot, 
    // but the easiest is just resetting the dragging offset to the center of the swapped dimensions
    const msX = rect.left + dragOffsetX;
    const msY = rect.top + dragOffsetY;
    dragOffsetX = rect.width / 2;
    dragOffsetY = rect.height / 2;
    draggingDomino.el.style.left = msX - dragOffsetX + 'px';
    draggingDomino.el.style.top = msY - dragOffsetY + 'px';
  }
});

// Event listeners for buttons
elBtnNew.addEventListener('click', () => {
  // Reset DOM fragments
  dominoes.forEach(d => {
    if (d.el && d.el.parentNode) {
      d.el.parentNode.removeChild(d.el);
    }
  });
  loadPuzzle();
});

elBtnReset.addEventListener('click', () => {
  dominoes.forEach(d => {
    if (!d.inPool) {
      board.lift(d);
    }
    returnToPool(d);
  });
  updateIndicator();
});

// Boot
initGridDOM();
loadPuzzle();
