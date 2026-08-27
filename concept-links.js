(() => {
  function currentInsightId() {
    const marker = Array.from(document.querySelectorAll('.site-footer span'))
      .find((span) => span.textContent.trim().startsWith('Explainer:'));
    return marker ? marker.textContent.split(':').slice(1).join(':').trim() : null;
  }

  async function fetchIndex() {
    const response = await fetch('../../knowledge/concepts/index.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`concept index: HTTP ${response.status}`);
    return response.json();
  }

  function normalize(value) {
    return String(value || '').trim().toLowerCase();
  }

  function addConceptLinks(records, insightId) {
    const supported = records.filter((record) => (record.supporting_insight_ids || []).includes(insightId));
    if (!supported.length) return;
    const byLabel = new Map(supported.map((record) => [normalize(record.label), record]));
    document.querySelectorAll('#concepts .concept-card').forEach((card) => {
      const heading = card.querySelector('h3');
      const record = byLabel.get(normalize(heading?.textContent));
      if (!record || card.querySelector('.concept-page-link')) return;
      const link = document.createElement('a');
      link.className = 'concept-page-link';
      link.href = `../../knowledge/concepts/${record.id}/`;
      link.textContent = 'Open concept →';
      card.appendChild(link);
    });
  }

  function addRelatedExplainers(records, insightId) {
    const relevant = records.filter((record) => (record.supporting_insight_ids || []).includes(insightId));
    const related = new Map();
    relevant.forEach((record) => {
      (record.related_explainers || []).forEach((item) => {
        const entry = related.get(item.insight_id) || {
          insight_id: item.insight_id,
          title: item.title,
          slug: item.slug,
          concepts: new Set(),
        };
        entry.concepts.add(record.label);
        related.set(item.insight_id, entry);
      });
    });
    if (!related.size || document.getElementById('related-explainers')) return;

    const sources = document.getElementById('sources');
    if (!sources) return;
    const section = document.createElement('section');
    section.id = 'related-explainers';
    section.className = 'detail-section wrap related-explainers-section';
    section.innerHTML = '<p class="kicker">RELATED EXPLAINERS</p><h2>Connected by published graph relations.</h2>';
    const grid = document.createElement('div');
    grid.className = 'related-explainer-grid';
    Array.from(related.values())
      .sort((a, b) => a.title.localeCompare(b.title))
      .forEach((item) => {
        const card = document.createElement('article');
        card.className = 'related-explainer-card';
        const title = document.createElement('h3');
        const link = document.createElement('a');
        link.href = `../../explainers/${item.slug}/`;
        link.textContent = item.title;
        title.appendChild(link);
        const note = document.createElement('p');
        note.textContent = `Connected through ${Array.from(item.concepts).sort().join(', ')}.`;
        card.append(title, note);
        grid.appendChild(card);
      });
    section.appendChild(grid);
    sources.parentNode.insertBefore(section, sources);
  }

  async function buildConceptNavigation() {
    if (!document.body.classList.contains('generated-page')) return;
    const insightId = currentInsightId();
    if (!insightId) return;
    try {
      const payload = await fetchIndex();
      const records = payload.records || [];
      addConceptLinks(records, insightId);
      addRelatedExplainers(records, insightId);
    } catch (_) {
      // Public concept navigation is supplemental; generated explainers remain usable without it.
    }
  }

  buildConceptNavigation();
})();
