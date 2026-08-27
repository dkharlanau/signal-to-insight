(() => {
  const BASE_VISUAL_SELECTOR = '#model .model-flow, #model .visual-sequence, #model .visual-layers, #model .visual-compare, #model .visual-decision';

  function currentInsightId() {
    const marker = Array.from(document.querySelectorAll('.site-footer span'))
      .find((span) => span.textContent.trim().startsWith('Explainer:'));
    return marker ? marker.textContent.split(':').slice(1).join(':').trim() : null;
  }

  async function fetchExtensions() {
    const response = await fetch('../../data/visual-extensions.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`visual extensions: HTTP ${response.status}`);
    return response.json();
  }

  function fallbackBlock(record) {
    const details = document.createElement('details');
    details.className = 'visual-extension-fallback';
    const summary = document.createElement('summary');
    summary.textContent = record.fallback.title;
    const list = document.createElement('ol');
    (record.fallback.items || []).forEach((text) => {
      const item = document.createElement('li');
      item.textContent = text;
      list.appendChild(item);
    });
    details.append(summary, list);
    return details;
  }

  function nodeMap(nodes) {
    return new Map((nodes || []).map((node) => [node.id, node]));
  }

  function outgoingMap(edges) {
    const map = new Map();
    (edges || []).forEach((edge) => {
      if (!map.has(edge.from)) map.set(edge.from, []);
      map.get(edge.from).push(edge);
    });
    return map;
  }

  function treeLayers(rootId, nodes, edges) {
    const depths = new Map([[rootId, 0]]);
    const queue = [rootId];
    const outgoing = outgoingMap(edges);
    while (queue.length) {
      const current = queue.shift();
      const depth = depths.get(current) || 0;
      (outgoing.get(current) || []).forEach((edge) => {
        if (!depths.has(edge.to)) {
          depths.set(edge.to, depth + 1);
          queue.push(edge.to);
        }
      });
    }
    const layers = new Map();
    nodes.forEach((node) => {
      const depth = depths.get(node.id) ?? 0;
      if (!layers.has(depth)) layers.set(depth, []);
      layers.get(depth).push(node);
    });
    return Array.from(layers.entries()).sort((a, b) => a[0] - b[0]);
  }

  function branchList(node, edges, nodes) {
    const outgoing = edges.filter((edge) => edge.from === node.id);
    if (!outgoing.length) return null;
    const list = document.createElement('ul');
    list.className = 'visual-branches';
    outgoing.forEach((edge) => {
      const target = nodes.get(edge.to);
      const item = document.createElement('li');
      const label = document.createElement('span');
      label.textContent = edge.label;
      const destination = document.createElement('strong');
      destination.textContent = `→ ${target?.title || edge.to}`;
      item.append(label, destination);
      list.appendChild(item);
    });
    return list;
  }

  function cardForNode(node, edges, nodes) {
    const card = document.createElement('article');
    card.className = `visual-extension-node visual-kind-${node.kind || 'step'}`;
    const label = document.createElement('span');
    label.className = 'visual-extension-label';
    label.textContent = node.label;
    const title = document.createElement('h3');
    title.textContent = node.title;
    const text = document.createElement('p');
    text.textContent = node.text;
    card.append(label, title, text);
    const branches = branchList(node, edges, nodes);
    if (branches) card.appendChild(branches);
    return card;
  }

  function renderDecisionTree(record) {
    const data = record.decision_tree;
    const nodes = nodeMap(data.nodes);
    const root = document.createElement('div');
    root.className = 'visual-extension visual-decision-tree-v2';
    root.setAttribute('role', 'group');
    root.setAttribute('aria-label', data.title);

    const heading = document.createElement('div');
    heading.className = 'visual-extension-heading';
    heading.innerHTML = '<span>DECISION TREE</span>';
    const h3 = document.createElement('h3');
    h3.textContent = data.title;
    heading.appendChild(h3);
    root.appendChild(heading);

    const layers = document.createElement('div');
    layers.className = 'visual-tree-layers';
    treeLayers(data.root_id, data.nodes, data.edges).forEach(([depth, layerNodes]) => {
      const layer = document.createElement('div');
      layer.className = 'visual-tree-layer';
      layer.dataset.depth = String(depth);
      layerNodes.forEach((node) => layer.appendChild(cardForNode(node, data.edges, nodes)));
      layers.appendChild(layer);
    });
    root.append(layers, fallbackBlock(record));
    return root;
  }

  function renderStateTransition(record) {
    const data = record.state_transition;
    const nodes = nodeMap(data.states);
    const root = document.createElement('div');
    root.className = 'visual-extension visual-state-transition-v2';
    root.setAttribute('role', 'group');
    root.setAttribute('aria-label', data.title);

    const heading = document.createElement('div');
    heading.className = 'visual-extension-heading';
    heading.innerHTML = '<span>STATE TRANSITION</span>';
    const h3 = document.createElement('h3');
    h3.textContent = data.title;
    heading.appendChild(h3);
    root.appendChild(heading);

    const grid = document.createElement('div');
    grid.className = 'visual-state-grid';
    data.states.forEach((state) => {
      const card = cardForNode(state, data.transitions, nodes);
      if (state.id === data.initial_state_id) card.dataset.initial = 'true';
      grid.appendChild(card);
    });
    root.append(grid, fallbackBlock(record));
    return root;
  }

  function renderSourceFigure(record) {
    const data = record.source_figure;
    const figure = document.createElement('figure');
    figure.className = 'visual-extension source-figure-v2';

    const heading = document.createElement('div');
    heading.className = 'visual-extension-heading';
    heading.innerHTML = '<span>SOURCE FIGURE</span>';
    const h3 = document.createElement('h3');
    h3.textContent = 'Original visual from the source authors';
    heading.appendChild(h3);

    const link = document.createElement('a');
    link.href = data.source_page;
    link.target = '_blank';
    link.rel = 'noreferrer';
    link.className = 'source-figure-link';

    const image = document.createElement('img');
    image.src = data.url;
    image.alt = data.alt;
    image.loading = 'lazy';
    image.decoding = 'async';
    image.referrerPolicy = 'no-referrer';
    link.appendChild(image);

    const caption = document.createElement('figcaption');
    const main = document.createElement('p');
    main.textContent = data.caption;
    const attribution = document.createElement('small');
    attribution.textContent = `${data.attribution} · source-hosted asset · not mirrored by Signal to Insight`;
    caption.append(main, attribution);

    const fallback = fallbackBlock(record);
    fallback.classList.add('source-figure-error-fallback');
    fallback.hidden = true;
    image.addEventListener('error', () => {
      link.hidden = true;
      fallback.hidden = false;
    });

    figure.append(heading, link, caption, fallback);
    return figure;
  }

  function install(record) {
    const model = document.getElementById('model');
    const base = document.querySelector(BASE_VISUAL_SELECTOR);
    if (!model || !base) return;

    let extension;
    if (record.primitive === 'decision_tree') extension = renderDecisionTree(record);
    else if (record.primitive === 'state_transition') extension = renderStateTransition(record);
    else if (record.primitive === 'source_figure') extension = renderSourceFigure(record);
    else return;

    const reason = document.createElement('p');
    reason.className = 'visual-extension-reason';
    reason.textContent = record.reason;
    extension.appendChild(reason);

    if (record.primitive === 'source_figure' || record.replaces_base_dominant === false) {
      base.insertAdjacentElement('afterend', extension);
    } else {
      base.replaceWith(extension);
    }
  }

  async function build() {
    if (!document.body.classList.contains('generated-page')) return;
    const id = currentInsightId();
    if (!id) return;
    try {
      const payload = await fetchExtensions();
      const record = (payload.records || []).find((item) => item.insight_id === id);
      if (record) install(record);
    } catch (_) {
      // The base generated visual remains intact when the extension layer is unavailable.
    }
  }

  build();
})();
