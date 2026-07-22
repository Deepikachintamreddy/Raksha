document.addEventListener('DOMContentLoaded', async () => {
  const statusEl = document.getElementById('engineStatus');
  const dashboardBtn = document.getElementById('openWebDashboard');

  try {
    const res = await fetch('http://localhost:8000/health');
    if (res.ok) {
      const data = await res.json();
      statusEl.textContent = `🟢 Connected (${data.total_cases_analyzed} cases logged)`;
      statusEl.style.color = '#4ade80';
    } else {
      statusEl.textContent = '🟡 Server response error';
      statusEl.style.color = '#facc15';
    }
  } catch (err) {
    statusEl.textContent = '🔴 Offline — Start backend on port 8000';
    statusEl.style.color = '#f87171';
  }

  dashboardBtn.addEventListener('click', () => {
    chrome.tabs.create({ url: 'http://localhost:8000' });
  });
});
