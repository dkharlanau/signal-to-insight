const progressBar = document.getElementById('progressBar');

if (document.body.classList.contains('generated-page')) {
  const explainerStyles = document.createElement('link');
  explainerStyles.rel = 'stylesheet';
  explainerStyles.href = '../../explainer.css';
  document.head.appendChild(explainerStyles);

  const visualPlanStyles = document.createElement('link');
  visualPlanStyles.rel = 'stylesheet';
  visualPlanStyles.href = '../../visual-plan.css';
  document.head.appendChild(visualPlanStyles);

  const retentionStyles = document.createElement('link');
  retentionStyles.rel = 'stylesheet';
  retentionStyles.href = '../../retention.css';
  document.head.appendChild(retentionStyles);
}

if (document.body.classList.contains('preview-page')) {
  const previewStyles = document.createElement('link');
  previewStyles.rel = 'stylesheet';
  previewStyles.href = '../../preview.css';
  document.head.appendChild(previewStyles);
}

function relativeRoot() {
  if (document.body.classList.contains('generated-page') || document.body.classList.contains('preview-page')) return '../../';
  if (document.body.classList.contains('library-page')) return '../';
  return '';
}

function ensurePrimaryKnowledgeLinks() {
  const nav = document.querySelector('.site-header nav');
  if (!nav) return;
  const labels = new Set(Array.from(nav.querySelectorAll('a')).map((link) => link.textContent.trim().toLowerCase()));
  const root = relativeRoot();
  const additions = [
    ['Library', `${root}library/`],
    ['Knowledge', `${root}knowledge/`],
  ];
  additions.forEach(([label, href]) => {
    if (labels.has(label.toLowerCase())) return;
    const link = document.createElement('a');
    link.href = href;
    link.textContent = label;
    nav.appendChild(link);
  });
}

function updateProgress() {
  if (!progressBar) return;
  const scrollable = document.documentElement.scrollHeight - window.innerHeight;
  const ratio = scrollable > 0 ? window.scrollY / scrollable : 0;
  progressBar.style.width = `${Math.min(100, Math.max(0, ratio * 100))}%`;
}

function explainerId() {
  const footerSpans = Array.from(document.querySelectorAll('.site-footer span'));
  const marker = footerSpans.find((span) => span.textContent.trim().startsWith('Explainer:'));
  if (marker) return marker.textContent.split(':').slice(1).join(':').trim();
  const parts = window.location.pathname.split('/').filter(Boolean);
  return parts[parts.length - 1] || 'unknown';
}

function safeStorageGet(key) {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : {};
  } catch (_) {
    return {};
  }
}

function safeStorageSet(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch (_) {
    return false;
  }
}

function formatRecallDate(value) {
  try {
    return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value));
  } catch (_) {
    return new Date(value).toLocaleDateString();
  }
}

function addRecallNavLink() {
  const nav = document.querySelector('.site-header nav');
  if (!nav || nav.querySelector('a[href="#recall"]')) return;
  const link = document.createElement('a');
  link.href = '#recall';
  link.textContent = 'Recall';
  const sources = nav.querySelector('a[href="#sources"]');
  if (sources) nav.insertBefore(link, sources);
  else nav.appendChild(link);
}

function buildRetentionLoop() {
  if (!document.body.classList.contains('generated-page')) return;
  if (document.getElementById('recall')) return;

  const actions = document.getElementById('actions');
  const sources = document.getElementById('sources');
  if (!actions || !sources) return;

  const title = document.querySelector('.detail-hero h1')?.textContent.trim() || 'this model';
  const coreColumns = document.querySelectorAll('#model .core-map > div');
  const problem = coreColumns[0]?.querySelector('p')?.textContent.trim() || 'Reconstruct the source problem.';
  const thesis = coreColumns[1]?.querySelector('p')?.textContent.trim() || 'Reconstruct the source thesis or mechanism.';
  const topics = Array.from(coreColumns[2]?.querySelectorAll('li') || []).slice(0, 2).map((item) => item.textContent.trim());
  const limitation = document.querySelector('.limitation-list li')?.textContent.trim() || 'Name one boundary where the model stops being sufficient.';

  const section = document.createElement('section');
  section.id = 'recall';
  section.className = 'detail-section wrap retention-section';
  section.innerHTML = `
    <div class="retention-intro">
      <div><p class="kicker">RECALL LATER</p><h2>Can the model survive without the page?</h2></div>
      <p>Attempt reconstruction before rereading. This is a small retention experiment, not a quiz bank or an optimized spaced-repetition algorithm.</p>
    </div>
    <div class="retention-card">
      <div class="retention-practice">
        <span class="retention-label">RECONSTRUCT BEFORE REOPENING</span>
        <h3 data-retention-prompt></h3>
        <p>Say it aloud or write it below. Aim for the structure, not exact wording.</p>
        <textarea class="retention-draft" aria-label="Your recall attempt" placeholder="Problem → mechanism / thesis → result or implication → one boundary. This text is not saved or sent anywhere."></textarea>
        <div class="retention-controls" aria-label="Schedule another recall">
          <button type="button" class="retention-button" data-retention-days="2">Review in 2 days</button>
          <button type="button" class="retention-button" data-retention-days="7">Review in 1 week</button>
        </div>
        <p class="retention-status" data-retention-status aria-live="polite"></p>
        <p class="retention-note">Only schedule/result metadata is stored locally in this browser. Your reconstruction text is never stored by this page.</p>
      </div>
      <details class="retention-answer">
        <summary>Reveal answer key after attempting recall</summary>
        <ol data-retention-answer></ol>
        <div class="retention-results" aria-label="Record recall result">
          <button type="button" class="retention-button" data-retention-result="recalled">I recalled the model</button>
          <button type="button" class="retention-button" data-retention-result="missed">I missed pieces</button>
          <button type="button" class="retention-button is-secondary" data-retention-clear>Clear local state</button>
        </div>
      </details>
    </div>`;

  const prompt = section.querySelector('[data-retention-prompt]');
  prompt.textContent = `Without looking back, reconstruct “${title}”: what problem is being solved, what mechanism or thesis matters, what changes as a result, and where does the model break?`;

  const answerList = section.querySelector('[data-retention-answer]');
  const answers = [
    `Problem — ${problem}`,
    `Thesis / mechanism — ${thesis}`,
    topics.length ? `Anchors — ${topics.join(' · ')}` : 'Anchors — recall two concepts or components that make the model work.',
    `Boundary — ${limitation}`,
  ];
  answers.forEach((answer) => {
    const item = document.createElement('li');
    item.textContent = answer;
    answerList.appendChild(item);
  });

  sources.parentNode.insertBefore(section, sources);
  addRecallNavLink();

  const id = explainerId();
  const storageKey = `signal-to-insight:retention:${id}`;
  let state = safeStorageGet(storageKey);
  const status = section.querySelector('[data-retention-status]');

  function renderStatus() {
    section.classList.remove('is-due');
    const parts = [];
    if (state.dueAt) {
      const due = new Date(state.dueAt);
      if (Date.now() >= due.getTime()) {
        section.classList.add('is-due');
        parts.push(`Due now — attempt recall before revealing the answer.`);
      } else {
        parts.push(`Next recall: ${formatRecallDate(state.dueAt)}.`);
      }
    } else {
      parts.push('Not scheduled yet.');
    }
    if (state.lastAttemptAt && state.lastResult) {
      const result = state.lastResult === 'recalled' ? 'model recalled' : 'missed pieces';
      parts.push(`Last attempt: ${result} · ${formatRecallDate(state.lastAttemptAt)}.`);
    }
    status.textContent = parts.join(' ');
  }

  section.querySelectorAll('[data-retention-days]').forEach((button) => {
    button.addEventListener('click', () => {
      const days = Number(button.dataset.retentionDays);
      state.dueAt = new Date(Date.now() + days * 24 * 60 * 60 * 1000).toISOString();
      state.scheduledDays = days;
      safeStorageSet(storageKey, state);
      renderStatus();
    });
  });

  section.querySelectorAll('[data-retention-result]').forEach((button) => {
    button.addEventListener('click', () => {
      state.lastAttemptAt = new Date().toISOString();
      state.lastResult = button.dataset.retentionResult;
      state.dueAt = null;
      safeStorageSet(storageKey, state);
      renderStatus();
    });
  });

  section.querySelector('[data-retention-clear]').addEventListener('click', () => {
    state = {};
    try { localStorage.removeItem(storageKey); } catch (_) {}
    renderStatus();
  });

  renderStatus();
}

ensurePrimaryKnowledgeLinks();
buildRetentionLoop();
window.addEventListener('scroll', updateProgress, { passive: true });
window.addEventListener('resize', updateProgress);
updateProgress();
