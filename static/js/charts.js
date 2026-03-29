var _perfCharts = {};

function destroyChart(key) {
  if (_perfCharts[key]) { _perfCharts[key].destroy(); delete _perfCharts[key]; }
}

function isDark() {
  return document.documentElement.getAttribute('data-theme') === 'dark';
}

function chartColors() {
  var dark = isDark();
  return {
    text:    dark ? '#94A3B8' : '#64748B',
    grid:    dark ? 'rgba(255,255,255,0.05)' : 'rgba(13,31,53,0.06)',
    tooltip: dark ? '#131D28' : '#FFFFFF',
    border:  dark ? '#253448' : '#D8DCE4',
  };
}

/* Animated count-up */
function countUp(el, target, suffix) {
  suffix = suffix || '';
  var start = 0;
  var duration = 700;
  var startTime = null;
  function step(ts) {
    if (!startTime) startTime = ts;
    var progress = Math.min((ts - startTime) / duration, 1);
    var ease = 1 - Math.pow(1 - progress, 3); // easeOutCubic
    el.textContent = Math.round(ease * target) + suffix;
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

/* Gradient helper */
function makeGradient(ctx, color1, color2) {
  var g = ctx.createLinearGradient(0, 0, 0, 300);
  g.addColorStop(0, color1);
  g.addColorStop(1, color2);
  return g;
}

/* Default animation options */
var ANIM = { duration: 800, easing: 'easeOutQuart' };

var baseTooltip = function() {
  var c = chartColors();
  return {
    backgroundColor: c.tooltip,
    titleColor: c.text,
    bodyColor: c.text,
    borderColor: c.border,
    borderWidth: 1,
    padding: 10,
    cornerRadius: 8,
    boxPadding: 4,
  };
};

function loadPerformance() {
  fetch('/performance/data')
    .then(function(r) { return r.json(); })
    .then(function(data) { renderCharts(data); })
    .catch(function(e) { console.error('performance data error', e); });
}

function renderCharts(data) {
  var colors = chartColors();
  var total = data.active_count + data.completed_count;
  var rate = total > 0 ? Math.round(data.completed_count / total * 100) : 0;

  /* ── KPI count-up ── */
  var elActive    = document.getElementById('perf-active');
  var elCompleted = document.getElementById('perf-completed');
  var elRate      = document.getElementById('perf-rate');
  var elTotal     = document.getElementById('perf-total');
  var elPct       = document.getElementById('perf-donut-pct');

  if (elActive)    countUp(elActive,    data.active_count);
  if (elCompleted) countUp(elCompleted, data.completed_count);
  if (elRate)      countUp(elRate,      rate, '%');
  if (elTotal)     countUp(elTotal,     total);
  if (elPct)       countUp(elPct,       rate, '%');

  /* ── Donut ── */
  destroyChart('donut');
  var ctxD = document.getElementById('chart-donut');
  if (ctxD) {
    _perfCharts['donut'] = new Chart(ctxD, {
      type: 'doughnut',
      data: {
        labels: ['Concluídas', 'Ativas'],
        datasets: [{
          data: [data.completed_count, data.active_count],
          backgroundColor: ['#0B8B78', '#C0392B'],
          hoverBackgroundColor: ['#097366', '#A93226'],
          borderWidth: 0,
          hoverOffset: 6,
        }]
      },
      options: {
        cutout: '72%',
        animation: ANIM,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { color: colors.text, font: { size: 12 }, padding: 16, usePointStyle: true, pointStyleWidth: 10 }
          },
          tooltip: baseTooltip(),
        }
      }
    });
  }

  /* ── Barras: por prioridade ── */
  destroyChart('priority');
  var ctxP = document.getElementById('chart-priority');
  if (ctxP) {
    var pri = data.priority_breakdown;
    var ctxPCanvas = ctxP.getContext('2d');
    _perfCharts['priority'] = new Chart(ctxP, {
      type: 'bar',
      data: {
        labels: ['Crítica', 'Urgente', 'Normal'],
        datasets: [
          {
            label: 'Ativas',
            data: [pri.active.critica, pri.active.urgente, pri.active.normal],
            backgroundColor: [
              'rgba(192,57,43,0.80)', 'rgba(196,125,26,0.75)', 'rgba(138,155,176,0.65)'
            ],
            hoverBackgroundColor: ['#C0392B', '#C47D1A', '#8A9BB0'],
            borderRadius: 6,
            borderSkipped: false,
          },
          {
            label: 'Concluídas',
            data: [pri.completed.critica, pri.completed.urgente, pri.completed.normal],
            backgroundColor: [
              'rgba(11,139,120,0.75)', 'rgba(11,139,120,0.52)', 'rgba(11,139,120,0.32)'
            ],
            hoverBackgroundColor: ['#0B8B78', '#0D9E8A', '#10B09A'],
            borderRadius: 6,
            borderSkipped: false,
          }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: true,
        animation: ANIM,
        scales: {
          x: {
            stacked: true,
            ticks: { color: colors.text, font: { size: 12 } },
            grid: { color: colors.grid },
            border: { color: colors.grid },
          },
          y: {
            stacked: true,
            ticks: { color: colors.text, font: { size: 12 }, stepSize: 1 },
            grid: { color: colors.grid },
            border: { color: colors.grid },
          }
        },
        plugins: {
          legend: { labels: { color: colors.text, usePointStyle: true, pointStyleWidth: 10 } },
          tooltip: baseTooltip(),
        }
      }
    });
  }

  /* ── Barras horizontais: por projeto ── */
  destroyChart('project');
  var ctxPj = document.getElementById('chart-project');
  if (ctxPj && data.project_breakdown && data.project_breakdown.length > 0) {
    var labels        = data.project_breakdown.map(function(p) { return p.name; });
    var activeVals    = data.project_breakdown.map(function(p) { return p.active; });
    var completedVals = data.project_breakdown.map(function(p) { return p.completed; });
    var barH = Math.max(200, data.project_breakdown.length * 44);
    ctxPj.parentElement.style.maxHeight = barH + 'px';
    ctxPj.style.height = barH + 'px';

    _perfCharts['project'] = new Chart(ctxPj, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Ativas',
            data: activeVals,
            backgroundColor: 'rgba(192,57,43,0.75)',
            hoverBackgroundColor: '#C0392B',
            borderRadius: 5,
            borderSkipped: false,
          },
          {
            label: 'Concluídas',
            data: completedVals,
            backgroundColor: 'rgba(11,139,120,0.68)',
            hoverBackgroundColor: '#0B8B78',
            borderRadius: 5,
            borderSkipped: false,
          }
        ]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        animation: ANIM,
        scales: {
          x: {
            stacked: true,
            ticks: { color: colors.text, font: { size: 12 }, stepSize: 1 },
            grid: { color: colors.grid },
            border: { color: colors.grid },
          },
          y: {
            stacked: true,
            ticks: { color: colors.text, font: { size: 12 } },
            grid: { display: false },
            border: { color: 'transparent' },
          }
        },
        plugins: {
          legend: { labels: { color: colors.text, usePointStyle: true, pointStyleWidth: 10 } },
          tooltip: baseTooltip(),
        }
      }
    });
  }
}
