(() => {
  const ORIGIN_LABELS = {
    source: 'Source',
    verification: 'Verification',
    project_interpretation: 'Project interpretation',
    prior_knowledge: 'Prior knowledge',
  };

  const PRIORITY_LABELS = {
    must_know_now: 'Must know now',
    learn_next: 'Learn next',
    optional_depth: 'Optional depth',
  };

  function root() {
    return '../../';
  }

  function currentInsightId() {
    const footerSpans = Array.from(document.querySelectorAll('.site-footer span'));
    const marker = footerSpans.find((span) => span.textContent.trim().startsWith('Explainer:'));
    return marker ? marker.textContent.split(':').slice(1).join(':').trim() : null;
  }

  async function fetchJson(path) {
    const response = await fetch(`${root()}${path}`, { cache: 'no-store' });
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
    return response.json();
  }

  function evidenceHref(item, insights) {
    if (item.kind !== 'prior_insight') return item.url || null;
    const prior = insights.get(item.insight_id);
    if (!prior) return null;
    if (prior.status === 'published') return `${root()}explainers/${prior.slug}/`;
    if (prior.status === 'review') return `${root()}previews/${prior.slug}/`;
    return null;
  }

  function evidenceTitle(item, insights, sources) {
    if (item.kind === 'prior_insight') {
      return insights.get(item.insight_id)?.title || item.insight_id || 'Prior insight';
    }
    if (item.source_id) return sources.get(item.source_id)?.title || item.source_id;
    return item.kind === 'verification' ? 'Verification source' : 'Primary source';
  }

  function addNavLink() {
    const nav = document.querySelector('.site-header nav');
    if (!nav || nav.querySelector('a[href="#evidence"]')) return;
    const link = document.createElement('a');
    link.href = '#evidence';
    link.textContent = 'Evidence';
    const sources = nav.querySelector('a[href="#sources"]');
    if (sources) nav.insertBefore(link, sources);
    else nav.appendChild(link);
  }

  function addPrerequisiteNavLink() {
    const nav = document.querySelector('.site-header nav');
    if (!nav || nav.querySelector('a[href="#prerequisites"]')) return;
    const link = document.createElement('a');
    link.href = '#prerequisites';
    link.textContent = 'Prereqs';
    const model = nav.querySelector('a[href="#model"]');
    if (model) nav.insertBefore(link, model);
    else nav.prepend(link);
  }

  function makeEvidenceItem(item, insights, sources) {
    const li = document.createElement('li');
    const href = evidenceHref(item, insights);
    const title = evidenceTitle(item, insights, sources);
    if (href) {
      const link = document.createElement('a');
      link.href = href;
      link.textContent = title;
      if (/^https?:\/\//.test(href)) {
        link.target = '_blank';
        link.rel = 'noreferrer';
      }
      li.appendChild(link);
    } else {
      const label = document.createElement('span');
      label.textContent = title;
      li.appendChild(label);
    }
    const locator = document.createElement('span');
    locator.className = 'evidence-locator';
    locator.textContent = item.locator;
    li.appendChild(locator);
    return li;
  }

  function appendPrerequisites(prerequisiteData, id, insights) {
    const record = (prerequisiteData.records || []).find((item) => item.insight_id === id);
    const modelSection = document.getElementById('model');
    if (!record || !modelSection || document.getElementById('prerequisites')) return;

    const section = document.createElement('section');
    section.id = 'prerequisites';
    section.className = 'detail-section wrap prerequisite-section';

    const intro = document.createElement('div');
    intro.className = 'prerequisite-intro';
    const heading = document.createElement('div');
    heading.innerHTML = '<p class="kicker">PREREQUISITES</p><h2>Only what the model actually depends on.</h2>';
    const summary = document.createElement('p');
    summary.textContent = record.summary;
    intro.append(heading, summary);
    section.appendChild(intro);

    const path = document.createElement('div');
    path.className = 'prerequisite-path';
    record.items.forEach((item, index) => {
      const card = document.createElement('article');
      card.className = `prerequisite-card state-${item.state}`;
      const order = document.createElement('span');
      order.className = 'prerequisite-order';
      order.textContent = String(index + 1).padStart(2, '0');
      const meta = document.createElement('div');
      meta.className = 'evidence-meta';
      const priority = document.createElement('span');
      priority.className = 'evidence-badge';
      priority.textContent = PRIORITY_LABELS[item.priority] || item.priority;
      const state = document.createElement('span');
      state.className = 'evidence-badge is-status';
      state.textContent = item.state.replaceAll('_', ' ');
      meta.append(priority, state);
      const title = document.createElement('h3');
      title.textContent = item.label;
      const reason = document.createElement('p');
      reason.textContent = item.reason;
      card.append(order, meta, title, reason);

      const resolution = item.resolution || {};
      if (resolution.kind === 'existing_explainer' && resolution.insight_id) {
        const target = insights.get(resolution.insight_id);
        if (target?.status === 'published') {
          const link = document.createElement('a');
          link.className = 'prerequisite-link';
          link.href = `${root()}explainers/${target.slug}/`;
          link.textContent = `Open prior explainer: ${target.title}`;
          card.appendChild(link);
        }
      } else if (resolution.kind === 'existing_concept' && resolution.target) {
        const label = document.createElement('span');
        label.className = 'prerequisite-link is-static';
        label.textContent = `Existing concept: ${resolution.target}`;
        card.appendChild(label);
      } else if (resolution.kind === 'learning_target' && resolution.target) {
        const label = document.createElement('span');
        label.className = 'prerequisite-link is-static';
        label.textContent = `Unresolved learning target: ${resolution.target}`;
        card.appendChild(label);
      }
      path.appendChild(card);
    });
    section.appendChild(path);
    modelSection.parentNode.insertBefore(section, modelSection);
    addPrerequisiteNavLink();
  }

  function appendKnowledgeReviews(section, reviewData, id) {
    const reviews = (reviewData.reviews || []).filter(
      (item) => item.trigger_insight_id === id && item.status === 'resolved',
    );
    if (!reviews.length) return;

    const intro = document.createElement('div');
    intro.className = 'evidence-review-intro';
    intro.innerHTML = '<p class="kicker">INTERPRETATION REVIEW</p><h2>Was this really a contradiction?</h2>';
    const note = document.createElement('p');
    note.textContent = 'Cross-source disagreements are resolved only after comparing subject, architectural layer and conditions. Different scope is not contradictory evidence.';
    intro.appendChild(note);
    section.appendChild(intro);

    const grid = document.createElement('div');
    grid.className = 'evidence-grid evidence-review-grid';
    reviews.forEach((review) => {
      const card = document.createElement('article');
      card.className = 'evidence-card';

      const meta = document.createElement('div');
      meta.className = 'evidence-meta';
      const candidate = document.createElement('span');
      candidate.className = 'evidence-badge';
      candidate.textContent = `${review.candidate_type} candidate`;
      const resolution = document.createElement('span');
      resolution.className = 'evidence-badge is-status';
      resolution.textContent = `resolved: ${review.resolution}`;
      meta.append(candidate, resolution);

      const title = document.createElement('h3');
      title.textContent = review.rationale;

      const list = document.createElement('ul');
      list.className = 'evidence-list';
      const scope = document.createElement('li');
      const scopeLabel = document.createElement('span');
      scopeLabel.textContent = `Scope assessment: ${review.scope_check.assessment.replaceAll('_', ' ')}`;
      const scopeDetail = document.createElement('span');
      scopeDetail.className = 'evidence-locator';
      scopeDetail.textContent = review.scope_check.explanation;
      scope.append(scopeLabel, scopeDetail);
      list.appendChild(scope);

      const change = document.createElement('li');
      const changeLabel = document.createElement('span');
      changeLabel.textContent = review.model_change.kind === 'none' ? 'Graph change: none required' : `Graph change: ${review.model_change.kind}`;
      const changeDetail = document.createElement('span');
      changeDetail.className = 'evidence-locator';
      changeDetail.textContent = review.model_change.reason;
      change.append(changeLabel, changeDetail);
      list.appendChild(change);

      card.append(meta, title, list);
      grid.appendChild(card);
    });
    section.appendChild(grid);
  }

  async function buildEvidenceTrace() {
    if (!document.body.classList.contains('generated-page')) return;
    if (document.getElementById('evidence')) return;
    const id = currentInsightId();
    const sourcesSection = document.getElementById('sources');
    if (!id || !sourcesSection) return;

    try {
      const [claimsData, insightsData, sourcesData, reviewData, prerequisiteData] = await Promise.all([
        fetchJson('data/claim-evidence.json'),
        fetchJson('data/insights.json'),
        fetchJson('data/sources.json'),
        fetchJson('data/knowledge-reviews.json'),
        fetchJson('data/prerequisite-maps.json'),
      ]);
      const record = (claimsData.records || []).find((item) => item.insight_id === id);
      if (!record || !(record.claims || []).length) return;

      const insights = new Map((insightsData.insights || []).map((item) => [item.id, item]));
      const sources = new Map((sourcesData.sources || []).map((item) => [item.id, item]));
      appendPrerequisites(prerequisiteData, id, insights);

      const section = document.createElement('section');
      section.id = 'evidence';
      section.className = 'detail-section wrap evidence-section';

      const intro = document.createElement('div');
      intro.className = 'evidence-intro';
      const heading = document.createElement('div');
      heading.innerHTML = '<p class="kicker">EVIDENCE TRACE</p><h2>What is source evidence — and what is interpretation?</h2>';
      const description = document.createElement('p');
      description.textContent = 'Important claims carry an origin, support status and locator. The trace stores paraphrases and references, not copied source text.';
      intro.append(heading, description);
      section.appendChild(intro);

      const grid = document.createElement('div');
      grid.className = 'evidence-grid';
      record.claims.forEach((claim) => {
        const card = document.createElement('article');
        card.className = 'evidence-card';

        const meta = document.createElement('div');
        meta.className = 'evidence-meta';
        const origin = document.createElement('span');
        origin.className = 'evidence-badge';
        origin.textContent = ORIGIN_LABELS[claim.origin] || claim.origin;
        const status = document.createElement('span');
        status.className = 'evidence-badge is-status';
        status.textContent = `${claim.status} · ${claim.impact} impact`;
        meta.append(origin, status);

        const title = document.createElement('h3');
        title.textContent = claim.text;

        const list = document.createElement('ul');
        list.className = 'evidence-list';
        (claim.evidence || []).forEach((item) => list.appendChild(makeEvidenceItem(item, insights, sources)));

        card.append(meta, title, list);
        if (claim.note) {
          const note = document.createElement('p');
          note.className = 'evidence-note';
          note.textContent = claim.note;
          card.appendChild(note);
        }
        grid.appendChild(card);
      });
      section.appendChild(grid);
      appendKnowledgeReviews(section, reviewData, id);
      sourcesSection.parentNode.insertBefore(section, sourcesSection);
      addNavLink();
    } catch (_) {
      // Evidence/review/prerequisite UI is supplemental; validated structured data remains canonical.
    }
  }

  buildEvidenceTrace();
})();
