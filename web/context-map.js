/* Small dependency-map renderer. No framework or external layout service. */
(function (scope, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else scope.contextMap = factory();
})(typeof window === 'undefined' ? globalThis : window, () => {
  const escape = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const cardWidth = 224, cardHeight = 92, columnStep = 336, rowStep = 124;

  function layout(documents, relationships) {
    const documentsById = new Map(documents.map(item => [item.id, item]));
    const edges = [...new Map(relationships
      .filter(edge => documentsById.has(edge.source_id) && documentsById.has(edge.target_id))
      .map(edge => [JSON.stringify([edge.source_id, edge.target_id, edge.kind]), edge])).values()];
    const ranks = new Map([...documentsById.keys()].map(id => [id, 0]));
    const dependencies = new Map([...documentsById.keys()].map(id => [id, new Set()]));
    const consumers = new Map([...documentsById.keys()].map(id => [id, new Set()]));
    for (const edge of edges.filter(edge => edge.kind !== 'references')) {
      dependencies.get(edge.source_id).add(edge.target_id);
      consumers.get(edge.target_id).add(edge.source_id);
    }
    const pending = new Map([...dependencies].map(([id, ids]) => [id, ids.size]));
    const queue = [...pending].filter(([, count]) => count === 0).map(([id]) => id);
    for (let index = 0; index < queue.length; index++) {
      const id = queue[index];
      for (const consumer of consumers.get(id)) {
        ranks.set(consumer, Math.max(ranks.get(consumer), ranks.get(id) + 1));
        pending.set(consumer, pending.get(consumer) - 1);
        if (pending.get(consumer) === 0) queue.push(consumer);
      }
    }
    // Keep cycles and their consumers visible in a final column instead of looping.
    const cycleRank = queue.length ? Math.max(...queue.map(id => ranks.get(id))) + 1 : 0;
    for (const [id, count] of pending) if (count > 0) ranks.set(id, cycleRank);
    const columns = [];
    for (const document of documentsById.values()) (columns[ranks.get(document.id)] ||= []).push(document);
    const rowCount = Math.max(1, ...columns.map(column => column.length));
    const nodes = columns.flatMap((column, rank) => column.map((document, row) => ({
      ...document, rank, x: 28 + rank * columnStep,
      y: 100 + ((rowCount - column.length) / 2 + row) * rowStep,
      width: cardWidth, height: cardHeight,
    })));
    const positions = new Map(nodes.map(node => [node.id, node]));
    const routedEdges = edges.map((edge, index) => {
      const source = positions.get(edge.source_id), target = positions.get(edge.target_id);
      const sourceY = source.y + cardHeight / 2, targetY = target.y + cardHeight / 2;
      let points, path;
      if (source.rank === target.rank + 1) {
        const startX = source.x, endX = target.x + cardWidth, middleX = (startX + endX) / 2;
        points = [[startX, sourceY], [middleX, sourceY], [middleX, targetY], [endX, targetY]];
        path = `M ${startX} ${sourceY} C ${middleX} ${sourceY} ${middleX} ${targetY} ${endX} ${targetY}`;
      } else if (source.rank === target.rank) {
        const endX = source.x + cardWidth, lane = endX + 20 + index % 4 * 9;
        // Separate ports keep self-links and cycles visible.
        points = [[endX, sourceY - 12], [lane, sourceY - 12], [lane, targetY + 12], [endX, targetY + 12]];
        path = points.map(([x, y], index) => `${index ? 'L' : 'M'} ${x} ${y}`).join(' ');
      } else {
        // Long links travel above the cards; vertical runs stay in column gaps.
        const startX = source.x, endX = target.x + cardWidth;
        const laneY = 20 + index % 6 * 9;
        points = [[startX, sourceY], [startX - 24, sourceY], [startX - 24, laneY], [endX + 24, laneY], [endX + 24, targetY], [endX, targetY]];
        path = points.map(([x, y], index) => `${index ? 'L' : 'M'} ${x} ${y}`).join(' ');
      }
      return {...edge, path, points};
    });
    return {nodes, edges: routedEdges, width: Math.max(320, columns.length * columnStep - 24), height: 100 + rowCount * rowStep};
  }

  function titleLines(title) {
    const words = String(title).split(/\s+/), lines = [''];
    for (const word of words) {
      const index = lines.length - 1;
      if ((lines[index] + ' ' + word).trim().length <= 25) lines[index] = (lines[index] + ' ' + word).trim();
      else if (lines.length < 2) lines.push(word);
      else {lines[1] += ' ' + word;}
    }
    return lines.filter(Boolean).map(line => line.length > 25 ? line.slice(0, 24) + '…' : line);
  }

  function render(documents, relationships, selectedId, zoom = 1) {
    if (!documents.length) return '';
    const map = layout(documents, relationships);
    const selected = map.nodes.find(node => node.id === selectedId);
    const dependencies = new Set(map.edges.filter(edge => edge.source_id === selectedId).map(edge => edge.target_id));
    const consumers = new Set(map.edges.filter(edge => edge.target_id === selectedId).map(edge => edge.source_id));
    const markers = ['normal', 'dependency', 'consumer'].map(kind => `<marker id="cp-arrow-${kind}" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z"/></marker>`).join('');
    const priority = edge => edge.source_id === selectedId ? 2 : edge.target_id === selectedId ? 1 : 0;
    const links = [...map.edges].sort((a, b) => priority(a) - priority(b)).map(edge => {
      const kind = edge.source_id === selectedId ? 'dependency' : edge.target_id === selectedId ? 'consumer' : 'normal';
      return `<path class="cp-edge cp-edge-${kind} ${edge.kind === 'references' ? 'cp-reference' : ''}" d="${edge.path}" marker-end="url(#cp-arrow-${kind})"><title>${escape(edge.source_id)} → ${escape(edge.target_id)}</title></path>`;
    }).join('');
    const cards = map.nodes.map(node => {
      const kind = node.id === selectedId ? 'selected' : dependencies.has(node.id) ? 'dependency' : consumers.has(node.id) ? 'consumer' : 'other';
      return `<g class="cp-node cp-node-${kind}" role="button" tabindex="0" aria-pressed="${node.id === selectedId}" aria-controls="context-detail" aria-label="Open ${escape(node.title)}, ${escape(node.domain)}, version ${node.revision}" data-cp-action="select" data-cp-map-node data-id="${escape(node.id)}" data-map-x="${node.x}" data-map-y="${node.y}"><title>${escape(node.title)}</title><rect x="${node.x}" y="${node.y}" width="${cardWidth}" height="${cardHeight}" rx="7"/>${titleLines(node.title).map((line, index) => `<text class="cp-node-title" x="${node.x + 14}" y="${node.y + 27 + index * 18}">${escape(line)}</text>`).join('')}<text class="cp-node-domain" x="${node.x + 14}" y="${node.y + 74}">${escape(node.domain)}</text><text class="cp-node-version" text-anchor="end" x="${node.x + cardWidth - 14}" y="${node.y + 74}">v${node.revision}</text></g>`;
    }).join('');
    const columnLabels = [...new Set(map.nodes.map(node => node.rank))].map(rank => `<text class="cp-map-column" x="${28 + rank * columnStep}" y="87">${rank ? `DEPENDENCY LEVEL ${rank}` : 'FOUNDATIONS'}</text>`).join('');
    return `<section class="panel cp-graph" data-context-map><div class="cp-map-title"><h2>Context map</h2><span>${map.nodes.length} pages · ${map.edges.length} links</span></div><div class="cp-map-header"><p>Page → dependency. Select a card to read its context.</p><div class="cp-map-controls" role="group" aria-label="Map controls"><button type="button" class="btn small" data-cp-action="map-zoom-out" aria-label="Zoom out" ${zoom <= MIN_ZOOM ? 'disabled' : ''}>−</button><output data-cp-zoom aria-label="Map zoom" aria-live="polite">${Math.round(zoom * 100)}%</output><button type="button" class="btn small" data-cp-action="map-zoom-in" aria-label="Zoom in" ${zoom >= MAX_ZOOM ? 'disabled' : ''}>+</button><button type="button" class="btn small" data-cp-action="map-reset" aria-label="Reset map to 100%">Reset</button><button type="button" class="btn small" data-cp-action="map-fit">Fit map</button></div></div><div class="cp-map-viewport" tabindex="0" role="region" aria-label="Interactive context map" aria-describedby="cp-map-help"><svg width="100%" height="100%" data-map-width="${map.width}" data-map-height="${map.height}" role="group" aria-label="Context dependency graph"><defs>${markers}</defs><g data-map-scene>${columnLabels}${links}${cards}</g></svg></div><div class="cp-map-footer"><p class="cp-map-selection" aria-live="polite">${selected ? `Selected: ${escape(selected.title)}` : 'Choose a context page'}</p><div class="cp-map-legend"><span class="cp-legend-selected">Selected</span><span class="cp-legend-dependency">Depends on</span><span class="cp-legend-consumer">Used by</span></div><p class="cp-map-hint" id="cp-map-help">Drag to pan · Wheel or pinch to zoom · + / − zoom · 0 reset · F fit · Arrow keys move between cards</p></div></section>`;
  }

  const MIN_ZOOM = 0.02, MAX_ZOOM = 4;
  const clampZoom = zoom => Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom));

  /** Attach gestures to this render only; destroy before replacing its DOM. */
  function mount(root, initialView, onChange = () => {}) {
    const viewport = root.querySelector('.cp-map-viewport');
    if (!viewport) return null;
    const svg = viewport.querySelector('svg'), scene = svg.querySelector('[data-map-scene]');
    const world = {width: Number(svg.dataset.mapWidth), height: Number(svg.dataset.mapHeight)};
    let view = initialView ? {...initialView} : {x: 0, y: 0, zoom: 1, fitted: true};
    let size = {width: viewport.clientWidth, height: viewport.clientHeight};
    let moved = false, ignoreClickUntil = 0;
    const pointers = new Map(), listeners = [];
    const listen = (type, handler, options) => {
      viewport.addEventListener(type, handler, options);
      listeners.push(() => viewport.removeEventListener(type, handler, options));
    };
    function update() {
      scene.setAttribute('transform', 'translate('+view.x+' '+view.y+') scale('+view.zoom+')');
      const output=root.querySelector('[data-cp-zoom]'), label=Math.round(view.zoom*100)+'%';
      if(output.textContent!==label)output.textContent=label;
      root.querySelector('[data-cp-action="map-zoom-out"]').disabled = view.zoom <= MIN_ZOOM;
      root.querySelector('[data-cp-action="map-zoom-in"]').disabled = view.zoom >= MAX_ZOOM;
      onChange({...view});
    }
    function center(zoom, fitted) {
      view = {zoom: clampZoom(zoom), x: 0, y: 0, fitted};
      view.x = (size.width-world.width*view.zoom)/2;
      view.y = (size.height-world.height*view.zoom)/2;
      update();
    }
    function fit() {
      if (size.width && size.height) center(Math.min(1, (size.width-32)/world.width, (size.height-32)/world.height), true);
    }
    function zoomAt(zoom, from, to = from) {
      const next = clampZoom(zoom), ratio = next/view.zoom;
      view = {zoom: next, x: to.x-(from.x-view.x)*ratio, y: to.y-(from.y-view.y)*ratio, fitted: false};
      update();
    }
    function command(action) {
      if (action === 'map-fit') return fit();
      if (action === 'map-reset') return center(1, false);
      zoomAt(view.zoom*(action === 'map-zoom-in' ? 1.25 : 0.8), {x: size.width/2, y: size.height/2});
    }
    function point(event) {
      const rect = viewport.getBoundingClientRect();
      return {x: event.clientX-rect.left-viewport.clientLeft, y: event.clientY-rect.top-viewport.clientTop};
    }
    function capture(id) {
      if (!viewport.hasPointerCapture(id)) viewport.setPointerCapture(id);
    }
    listen('pointerdown', event => {
      if (event.button !== 0 || pointers.size >= 2) return;
      if (!pointers.size) {moved = false; ignoreClickUntil = 0;}
      const position = point(event);
      pointers.set(event.pointerId, {...position, startX: position.x, startY: position.y});
      if (!event.target.closest('[data-cp-map-node]')) viewport.focus({preventScroll: true});
      if (pointers.size === 2) {
        moved = true;
        for (const id of pointers.keys()) capture(id);
        viewport.classList.add('cp-map-panning');
      }
    });
    listen('pointermove', event => {
      const previous = pointers.get(event.pointerId);
      if (!previous) return;
      const next = {...previous, ...point(event)}, before = [...pointers.values()];
      pointers.set(event.pointerId, next);
      if (!moved && Math.hypot(next.x-next.startX, next.y-next.startY) < 4) return;
      moved = true;
      capture(event.pointerId);
      viewport.classList.add('cp-map-panning');
      if (pointers.size === 2) {
        const after = [...pointers.values()];
        const midpoint = pair => ({x: (pair[0].x+pair[1].x)/2, y: (pair[0].y+pair[1].y)/2});
        const distance = pair => Math.hypot(pair[1].x-pair[0].x, pair[1].y-pair[0].y);
        zoomAt(view.zoom*(distance(before) > 1 ? distance(after)/distance(before) : 1), midpoint(before), midpoint(after));
      } else {
        view.x += next.x-previous.x; view.y += next.y-previous.y; view.fitted = false; update();
      }
      event.preventDefault();
    });
    function endPointer(event) {
      if (!pointers.has(event.pointerId)) return;
      pointers.delete(event.pointerId);
      if (moved) ignoreClickUntil = Date.now()+250;
      if (viewport.hasPointerCapture(event.pointerId)) viewport.releasePointerCapture(event.pointerId);
      if (!pointers.size) viewport.classList.remove('cp-map-panning');
    }
    listen('pointerup', endPointer);
    listen('pointercancel', endPointer);
    listen('lostpointercapture', endPointer);
    // A drag may end on a card. It must not open that card as a click.
    listen('click', event => {
      if (event.detail !== 0 && Date.now() < ignoreClickUntil) {
        event.preventDefault(); event.stopImmediatePropagation(); ignoreClickUntil = 0;
      }
    }, true);
    listen('wheel', event => {
      event.preventDefault();
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? size.height : 1;
      if (event.shiftKey || (!event.deltaY && event.deltaX)) {
        view.x -= (event.deltaX || event.deltaY)*unit; view.fitted = false; update();
      } else {
        const delta = Math.max(-600, Math.min(600, event.deltaY*unit));
        zoomAt(view.zoom*Math.exp(-delta*(event.ctrlKey ? 0.01 : 0.002)), point(event));
      }
    }, {passive: false});
    listen('keydown', event => {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const actions = {'+':'map-zoom-in', '=':'map-zoom-in', '-':'map-zoom-out', '0':'map-reset', 'f':'map-fit', 'F':'map-fit'};
      if (actions[event.key]) {event.preventDefault(); command(actions[event.key]);}
      else if (event.target === viewport) {
        const movement = {ArrowLeft:[40,0], ArrowRight:[-40,0], ArrowUp:[0,40], ArrowDown:[0,-40]}[event.key];
        if (movement) {event.preventDefault(); view.x += movement[0]; view.y += movement[1]; view.fitted = false; update();}
      }
    });
    listen('focusin', event => {
      const card = event.target.closest('[data-cp-map-node]');
      if (!card) return;
      const bounds = card.getBoundingClientRect(), frame = viewport.getBoundingClientRect(), gap = 12;
      const dx = bounds.left < frame.left+gap ? frame.left+gap-bounds.left : bounds.right > frame.right-gap ? frame.right-gap-bounds.right : 0;
      const dy = bounds.top < frame.top+gap ? frame.top+gap-bounds.top : bounds.bottom > frame.bottom-gap ? frame.bottom-gap-bounds.bottom : 0;
      if (dx || dy) {view.x += dx; view.y += dy; view.fitted = false; update();}
    });
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(() => {
      const next = {width: viewport.clientWidth, height: viewport.clientHeight};
      if (!next.width || !next.height || (next.width === size.width && next.height === size.height)) return;
      const previous = size; size = next;
      if (view.fitted) fit();
      else {view.x += (next.width-previous.width)/2; view.y += (next.height-previous.height)/2; update();}
    });
    observer?.observe(viewport);
    if (view.fitted) fit(); else update();
    return {
      command,
      getView: () => ({...view}),
      destroy() {
        observer?.disconnect();
        listeners.forEach(remove => remove());
        for (const id of pointers.keys()) if (viewport.hasPointerCapture(id)) viewport.releasePointerCapture(id);
        pointers.clear(); viewport.classList.remove('cp-map-panning');
      },
    };
  }

  return {layout, render, mount};
});
