const progressBar = document.getElementById('progressBar');

if (document.body.classList.contains('generated-page')) {
  const explainerStyles = document.createElement('link');
  explainerStyles.rel = 'stylesheet';
  explainerStyles.href = '../../explainer.css';
  document.head.appendChild(explainerStyles);
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