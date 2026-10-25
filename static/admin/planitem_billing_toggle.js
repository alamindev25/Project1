(function () {
  function toggleFields() {
    const typeEl = document.getElementById("id_billing_cycle_type");
    if (!typeEl) return;

    const presetRow = document.getElementById("id_billing_cycle")?.closest(".form-row");
    const customRow = document.getElementById("id_custom_days")?.closest(".form-row");

    if (!presetRow || !customRow) return;

    if (typeEl.value === "preset") {
      presetRow.style.display = "";
      customRow.style.display = "none";

      // optional: clear custom value when hidden
      document.getElementById("id_custom_days").value = "";
    } else if (typeEl.value === "custom") {
      presetRow.style.display = "none";
      customRow.style.display = "";

      // optional: clear preset value when hidden
      document.getElementById("id_billing_cycle").value = "";
    } else {
      // fallback: show both
      presetRow.style.display = "";
      customRow.style.display = "";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    toggleFields();
    const typeEl = document.getElementById("id_billing_cycle_type");
    if (typeEl) typeEl.addEventListener("change", toggleFields);
  });
})();