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

function updateProgress() {
  if (!progressBar) return;
  const scrollable = document.documentElement.scrollHeight - window.innerHeight;
  const ratio = scrollable > 0 ? window.scrollY / scrollable : 0;
  progressBar.style.width = `${Math.min(100, Math.max(0, ratio * 100))}%`;
}

window.addEventListener('scroll', updateProgress, { passive: true });
window.addEventListener('resize', updateProgress);
updateProgress();