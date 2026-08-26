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

ensurePrimaryKnowledgeLinks();
window.addEventListener('scroll', updateProgress, { passive: true });
window.addEventListener('resize', updateProgress);
updateProgress();
