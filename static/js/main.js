document.addEventListener("DOMContentLoaded", () => {
  const expenseForm = document.querySelector('form[action="/add_expense"]');
  const toast = document.getElementById("toast");
  const budgetBar = document.getElementById("budget-bar");

  if (expenseForm) {
    expenseForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const formData = new FormData(expenseForm);
      const res = await fetch("/add_expense", {
        method: "POST",
        body: formData,
        headers: { "X-Requested-With": "XMLHttpRequest" }
      });

      const data = await res.json();

      if (!res.ok) {
        showToast(data.error || "Error adding expense.");
        return;
      }

      // Update bar
      if (budgetBar && data.percent !== null) {
        budgetBar.style.width = data.percent + "%";
        budgetBar.className = ""; // reset
        if (data.percent > 75) budgetBar.classList.add("green");
        else if (data.percent > 30) budgetBar.classList.add("yellow");
        else if (data.percent > 10) budgetBar.classList.add("red");
        else budgetBar.classList.add("critical");
      }

      // Fetch quote
      const qRes = await fetch("/get_quote");
      const qData = await qRes.json();
      if (qData.quote) {
        showToast(qData.quote);
      }

      // Clear form
      expenseForm.reset();
    });
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add("show");
    setTimeout(() => {
      toast.classList.remove("show");
    }, 3000);
  }
});
