var _perfCharts = {};

function destroyChart(key) {
  if (_perfCharts[key]) {
    _perfCharts[key].destroy();
    delete _perfCharts[key];
  }
}

function isDark() {
  return document.documentElement.getAttribute('data-theme') === 'dark';
}

function chartColors() {
  return {
    text: isDark() ? '#94a3b8' : '#475569',
    grid: isDark() ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
  };
}

function loadPerformance() {
  fetch('/performance/data')
    .then(function(r) { return r.json(); })
    .then(function(data) { renderCharts(data); })
    .catch(function(e) { console.error('performance data error', e); });
}

function renderCharts(data) {
  var colors = chartColors();

  // Atualiza stats
  document.getElementById('perf-active').textContent = data.active_count;
  document.getElementById('perf-completed').textContent = data.completed_count;
  var total = data.active_count + data.completed_count;
  document.getElementById('perf-rate').textContent =
    total > 0 ? Math.round(data.completed_count / total * 100) + '%' : '—';

  // ── Donut: concluídas vs ativas ──
  destroyChart('donut');
  var ctxD = document.getElementById('chart-donut');
  if (ctxD) {
    _perfCharts['donut'] = new Chart(ctxD, {
      type: 'doughnut',
      data: {
        labels: ['Concluídas', 'Ativas'],
        datasets: [{
          data: [data.completed_count, data.active_count],
          backgroundColor: ['#22c55e', '#e63946'],
          borderWidth: 0,
        }]
      },
      options: {
        cutout: '70%',
        plugins: {
          legend: { position: 'bottom', labels: { color: colors.text, font: { size: 12 } } }
        }
      }
    });
  }

  // ── Barras: por prioridade ──
  destroyChart('priority');
  var ctxP = document.getElementById('chart-priority');
  if (ctxP) {
    var pri = data.priority_breakdown;
    _perfCharts['priority'] = new Chart(ctxP, {
      type: 'bar',
      data: {
        labels: ['Crítica', 'Urgente', 'Normal'],
        datasets: [
          {
            label: 'Ativas',
            data: [pri.active.critica, pri.active.urgente, pri.active.normal],
            backgroundColor: ['rgba(230,57,70,0.7)', 'rgba(244,162,97,0.7)', 'rgba(148,163,184,0.7)'],
          },
          {
            label: 'Concluídas',
            data: [pri.completed.critica, pri.completed.urgente, pri.completed.normal],
            backgroundColor: ['rgba(34,197,94,0.5)', 'rgba(34,197,94,0.4)', 'rgba(34,197,94,0.3)'],
          }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: true,
        scales: {
          x: { stacked: true, ticks: { color: colors.text }, grid: { color: colors.grid } },
          y: { stacked: true, ticks: { color: colors.text }, grid: { color: colors.grid } }
        },
        plugins: { legend: { labels: { color: colors.text } } }
      }
    });
  }

  // ── Barras horizontais: por projeto ──
  destroyChart('project');
  var ctxPj = document.getElementById('chart-project');
  if (ctxPj && data.project_breakdown && data.project_breakdown.length > 0) {
    var labels = data.project_breakdown.map(function(p) { return p.name; });
    var activeVals = data.project_breakdown.map(function(p) { return p.active; });
    var completedVals = data.project_breakdown.map(function(p) { return p.completed; });
    _perfCharts['project'] = new Chart(ctxPj, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          { label: 'Ativas', data: activeVals, backgroundColor: 'rgba(230,57,70,0.7)' },
          { label: 'Concluídas', data: completedVals, backgroundColor: 'rgba(34,197,94,0.5)' }
        ]
      },
      options: {
        indexAxis: 'y',
        responsive: true, maintainAspectRatio: true,
        scales: {
          x: { stacked: true, ticks: { color: colors.text }, grid: { color: colors.grid } },
          y: { stacked: true, ticks: { color: colors.text }, grid: { color: colors.grid } }
        },
        plugins: { legend: { labels: { color: colors.text } } }
      }
    });
  }
}
