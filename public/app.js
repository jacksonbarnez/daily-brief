const content = document.getElementById('content');
const updatedAt = document.getElementById('updatedAt');
const articleCount = document.getElementById('articleCount');
const sourceCount = document.getElementById('sourceCount');
const refreshButton = document.getElementById('refreshButton');
const installButton = document.getElementById('installButton');
const sectionTemplate = document.getElementById('sectionTemplate');
const cardTemplate = document.getElementById('cardTemplate');
const filterButtons = [...document.querySelectorAll('[data-filter]')];

let installPrompt = null;
let digestData = null;
let activeFilter = 'all';

async function loadDigest() {
  content.innerHTML = '<section class="loading-card"><p>Loading today\'s digest…</p></section>';

  try {
    const url = new URL('./data/digest.json', window.location.href);
    url.searchParams.set('ts', Date.now().toString());

    const response = await fetch(url.toString(), { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    digestData = await response.json();
    renderDigest();
  } catch (error) {
    console.error(error);
    content.innerHTML = `
      <section class="loading-card">
        <p>Could not load the digest right now.</p>
        <p class="subtext">Try again in a moment, or re-run the workflow from GitHub Actions.</p>
      </section>
    `;
  }
}

function renderDigest() {
  if (!digestData) return;

  updatedAt.textContent = new Date(digestData.generated_at).toLocaleString([], {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
  articleCount.textContent = String(digestData.stats.total_items);
  sourceCount.textContent = String(digestData.stats.total_sources);

  content.innerHTML = '';

  const filteredSections = digestData.sections.filter((section) => {
    if (activeFilter === 'all') return true;
    return section.id === activeFilter;
  });

  for (const section of filteredSections) {
    const fragment = sectionTemplate.content.cloneNode(true);
    fragment.querySelector('.section-eyebrow').textContent = section.id;
    fragment.querySelector('h2').textContent = section.title;
    const cards = fragment.querySelector('.cards');

    for (const item of section.items) {
      const card = cardTemplate.content.cloneNode(true);
      card.querySelector('.source-badge').textContent = item.source;
      card.querySelector('time').textContent = formatTime(item.published);
      card.querySelector('h3').textContent = item.title;
      card.querySelector('.summary').textContent = item.summary;
      card.querySelector('.category-pill').textContent = item.category;

      const link = card.querySelector('.read-link');
      link.href = item.url;

      cards.appendChild(card);
    }

    content.appendChild(fragment);
  }

  if (!filteredSections.length) {
    content.innerHTML = '<section class="loading-card"><p>No items matched that filter.</p></section>';
  }
}

function formatTime(value) {
  return new Date(value).toLocaleString([], {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

filterButtons.forEach((button) => {
  button.addEventListener('click', () => {
    activeFilter = button.dataset.filter;
    filterButtons.forEach((entry) => entry.classList.remove('active'));
    button.classList.add('active');
    renderDigest();
  });
});

refreshButton.addEventListener('click', loadDigest);

window.addEventListener('beforeinstallprompt', (event) => {
  event.preventDefault();
  installPrompt = event;
  installButton.classList.remove('hidden');
});

installButton.addEventListener('click', async () => {
  if (!installPrompt) return;
  installPrompt.prompt();
  await installPrompt.userChoice;
  installPrompt = null;
  installButton.classList.add('hidden');
});

if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      await navigator.serviceWorker.register('./service-worker.js', { scope: './' });
    } catch (error) {
      console.error('Service worker registration failed', error);
    }
  });
}

loadDigest();
