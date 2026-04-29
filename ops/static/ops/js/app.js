document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-open]').forEach(btn => btn.addEventListener('click', () => {
    const dialog = document.getElementById(btn.dataset.open);
    if (dialog) dialog.showModal();
  }));
  document.querySelectorAll('[data-close]').forEach(btn => btn.addEventListener('click', () => btn.closest('dialog')?.close()));

  document.querySelectorAll('.table-filter').forEach(input => {
    input.addEventListener('input', () => {
      const table = document.getElementById(input.dataset.table);
      const q = input.value.toLowerCase();
      table?.querySelectorAll('tbody tr').forEach(row => row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none');
    });
  });

  document.querySelectorAll('.data-table th').forEach((th, idx) => {
    th.addEventListener('click', () => {
      const table = th.closest('table');
      const tbody = table.querySelector('tbody');
      const rows = Array.from(tbody.querySelectorAll('tr')).filter(r => r.children.length > 1);
      const asc = th.dataset.asc !== 'true';
      th.dataset.asc = asc;
      rows.sort((a,b) => a.children[idx].textContent.trim().localeCompare(b.children[idx].textContent.trim(), undefined, {numeric:true}) * (asc ? 1 : -1));
      rows.forEach(r => tbody.appendChild(r));
    });
  });

  document.querySelectorAll('input[type="range"]').forEach(range => {
    const output = range.parentElement?.querySelector('output');
    range.addEventListener('input', () => { if (output) output.textContent = `${range.value}%`; });
  });

  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const panel = tab.closest('.panel');
      panel.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      panel.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      panel.querySelector(`#${tab.dataset.tab}`)?.classList.add('active');
    });
  });

  document.querySelectorAll('.copy-btn').forEach(btn => btn.addEventListener('click', async () => {
    await navigator.clipboard.writeText(btn.dataset.copy || '');
    btn.textContent = 'Copied';
  }));

  const chart = document.getElementById('dailyCostChart');
  if (chart && window.Chart) {
    const labels = JSON.parse(document.getElementById('chart-labels')?.textContent || '[]');
    const values = JSON.parse(document.getElementById('chart-values')?.textContent || '[]');
    new Chart(chart, {type:'line', data:{labels, datasets:[{label:'Daily labour cost', data:values, tension:.35}]}, options:{responsive:true, plugins:{legend:{display:false}}, scales:{y:{beginAtZero:true}}}});
  }

  function rainMoney(){
    for(let i=0;i<42;i++){
      const el=document.createElement('div');
      el.className='rain-money';
      el.textContent=['💸','💰','🪙'][Math.floor(Math.random()*3)];
      el.style.left=Math.random()*100+'vw';
      el.style.animationDelay=Math.random()*0.8+'s';
      document.body.appendChild(el);
      setTimeout(()=>el.remove(),2600);
    }
  }
  if (window.NEWLIGHT_RAIN_MONEY) rainMoney();
});
