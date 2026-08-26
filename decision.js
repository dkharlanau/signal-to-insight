(() => {
  const DECISION_LABELS = {
    consume: 'Consume the original',
    skim_selected_parts: 'Skim selected parts',
    explainer_is_enough: 'Explainer is enough',
    skip_for_now: 'Skip for now',
  };
  const FACTOR_LABELS = {
    novelty: 'Novelty',
    source_quality: 'Source quality',
    relevance: 'Relevance',
    practical_leverage: 'Practical leverage',
    compression_loss: 'Compression loss',
  };

  function currentInsightId() {
    const marker = Array.from(document.querySelectorAll('.site-footer span'))
      .find((span) => span.textContent.trim().startsWith('Explainer:'));
    return marker ? marker.textContent.split(':').slice(1).join(':').trim() : null;
  }

  async function fetchJson(path) {
    const response = await fetch(`../../${path}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
    return response.json();
  }

  function addNavLink() {
    const nav = document.querySelector('.site-header nav');
    if (!nav || nav.querySelector('a[href="#source-decision"]')) return;
    const link = document.createElement('a');
    link.href = '#source-decision';
    link.textContent = 'Decision';
    nav.prepend(link);
  }

  function claimIndex(claimData) {
    const map = new Map();
    (claimData.records || []).forEach((record) => {
      (record.claims || []).forEach((claim) => map.set(claim.id, claim));
    });
    return map;
  }

  function bestHref(part, claims) {
    for (const claimId of part.claim_refs || []) {
      const claim = claims.get(claimId);
      for (const evidence of claim?.evidence || []) {
        if (evidence.url) return evidence.url;
      }
    }
    return null;
  }

  async function buildSourceDecision() {
    if (!document.body.classList.contains('generated-page')) return;
    if (document.getElementById('source-decision')) return;
    const id = currentInsightId();
    const hero = document.querySelector('.detail-hero');
    if (!id || !hero) return;

    try {
      const [decisionData, claimData] = await Promise.all([
        fetchJson('data/source-decisions.json'),
        fetchJson('data/claim-evidence.json'),
      ]);
      const record = (decisionData.records || []).find((item) => item.insight_id === id);
      if (!record) return;
      const claims = claimIndex(claimData);

      const section = document.createElement('section');
      section.id = 'source-decision';
      section.className = 'source-decision-section wrap';

      const head = document.createElement('div');
      head.className = 'source-decision-head';
      const label = document.createElement('div');
      label.innerHTML = '<p class="kicker">SOURCE DECISION</p>';
      const content = document.createElement('div');
      const decision = document.createElement('span');
      decision.className = 'source-decision-badge';
      decision.textContent = DECISION_LABELS[record.decision] || record.decision;
      const title = document.createElement('h2');
      title.textContent = record.rationale;
      content.append(decision, title);
      head.append(label, content);
      section.appendChild(head);

      const factors = document.createElement('div');
      factors.className = 'source-decision-factors';
      Object.entries(FACTOR_LABELS).forEach(([key, factorLabel]) => {
        const factor = record[key];
        const card = document.createElement('article');
        card.innerHTML = `<span>${factorLabel}</span><strong>${factor.level}</strong><p></p>`;
        card.querySelector('p').textContent = factor.reason;
        factors.appendChild(card);
      });
      section.appendChild(factors);

      if ((record.selected_parts || []).length) {
        const skim = document.createElement('div');
        skim.className = 'source-decision-parts';
        const skimHead = document.createElement('p');
        skimHead.className = 'source-decision-parts-title';
        skimHead.textContent = 'Open only these parts';
        skim.appendChild(skimHead);
        const list = document.createElement('ol');
        record.selected_parts.forEach((part) => {
          const item = document.createElement('li');
          const href = bestHref(part, claims);
          const name = href ? document.createElement('a') : document.createElement('strong');
          if (href) {
            name.href = href;
            name.target = '_blank';
            name.rel = 'noreferrer';
          }
          name.textContent = part.label;
          const locator = document.createElement('span');
          locator.textContent = part.locator;
          const why = document.createElement('p');
          why.textContent = part.why;
          item.append(name, locator, why);
          list.appendChild(item);
        });
        skim.appendChild(list);
        section.appendChild(skim);
      } else {
        const note = document.createElement('p');
        note.className = 'source-decision-enough';
        note.textContent = 'For the current learning goal, no source section needs to be reopened unless you need methodological or implementation detail beyond this explainer.';
        section.appendChild(note);
      }

      hero.insertAdjacentElement('afterend', section);
      addNavLink();
    } catch (_) {
      // Structured decision data remains canonical; the card is a progressive enhancement.
    }
  }

  buildSourceDecision();
})();
