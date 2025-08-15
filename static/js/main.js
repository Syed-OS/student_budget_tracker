let categoryChart, dailyChart;

async function loadCharts() {
  const catCanvas = document.getElementById("categoryChart");
  const dayCanvas = document.getElementById("dailyChart");

  // Only try to render if canvases exist on this page
  if (!catCanvas && !dayCanvas) return;

  // Category chart
  if (catCanvas) {
    const catRes = await fetch("/stats/categories");
    const catData = await catRes.json();
    const catLabels = Object.keys(catData);
    const catValues = Object.values(catData);

    if (categoryChart) categoryChart.destroy();
    const catCtx = catCanvas.getContext("2d");
    categoryChart = new Chart(catCtx, {
      type: "pie",
      data: {
        labels: catLabels,
        datasets: [{
          data: catValues,
          backgroundColor: [
            "#3b82f6", "#f97316", "#22c55e", "#eab308", "#ef4444", "#a855f7"
          ]
        }]
      }
    });
  }

  // Daily cumulative chart
  if (dayCanvas) {
    const dayRes = await fetch("/stats/daily");
    const dayData = await dayRes.json();
    const dayLabels = Object.keys(dayData);
    const dayValues = Object.values(dayData);

    if (dailyChart) dailyChart.destroy();
    const dayCtx = dayCanvas.getContext("2d");
    dailyChart = new Chart(dayCtx, {
      type: "line",
      data: {
        labels: dayLabels,
        datasets: [{
          label: "Cumulative Spend",
          data: dayValues,
          fill: false,
          borderColor: "#3b82f6",
          tension: 0.1
        }]
      }
    });
  }
}

function setBarColorBy(percent, el) {
  el.className = ""; // reset classes
  if (percent > 75) el.classList.add("green");
  else if (percent > 30) el.classList.add("yellow");
  else if (percent > 10) el.classList.add("red");
  else el.classList.add("critical");
}

// NEW: set body background mood
function setBodyMoodBy(percent) {
  const body = document.body;
  body.classList.remove("mood-green", "mood-yellow", "mood-red", "mood-critical");
  if (percent > 75) body.classList.add("mood-green");
  else if (percent > 30) body.classList.add("mood-yellow");
  else if (percent > 10) body.classList.add("mood-red");
  else body.classList.add("mood-critical");
}

function showToast(message) {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3000);
}

document.addEventListener("DOMContentLoaded", () => {
  const expenseForm = document.querySelector('form[action="/add_expense"]');
  const budgetBar = document.getElementById("budget-bar");

  // INITIAL: set body mood from server-rendered percent (if present)
  const percentDiv = document.getElementById("percent-remaining");
  if (percentDiv) {
    const p = parseFloat(percentDiv.dataset.percent);
    if (!Number.isNaN(p)) setBodyMoodBy(p);
  }

  // Load charts (if present on the page)
  loadCharts();

  if (expenseForm) {
    expenseForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const formData = new FormData(expenseForm);
      const res = await fetch("/add_expense", {
        method: "POST",
        body: formData,
        headers: { "X-Requested-With": "XMLHttpRequest" }
      });

      let data;
      try { data = await res.json(); } catch (_) { data = {}; }

      if (!res.ok) {
        showToast(data.error || "Error adding expense.");
        return;
      }

      // ✅ Update Remaining and Total Spent instantly
      if (data.remaining !== null && data.remaining !== undefined) {
        const remainingEl = document.getElementById("remaining-amount");
        if (remainingEl) remainingEl.textContent = `$${parseFloat(data.remaining).toFixed(2)}`;
      }
      if (data.total_spent !== null && data.total_spent !== undefined) {
        const spentEl = document.getElementById("total-spent-amount");
        if (spentEl) spentEl.textContent = `$${parseFloat(data.total_spent).toFixed(2)}`;
      }

      // Update health bar + page mood
      if (budgetBar && data.percent !== null && data.percent !== undefined) {
        budgetBar.style.width = data.percent + "%";
        setBarColorBy(data.percent, budgetBar);
        setBodyMoodBy(data.percent);
      }

      // Fetch and show quote
      try {
        const qRes = await fetch("/get_quote");
        const qData = await qRes.json();
        if (qData.quote) showToast(qData.quote);
      } catch (_) {
        // non-fatal if quotes fail
      }

      // Clear form & refresh charts
      expenseForm.reset();
      loadCharts();
    });
  }
});
