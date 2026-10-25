(function () {
  function getMaxOrder(prefix) {
    let max = 1;

    document.querySelectorAll(`input[id^="id_${prefix}-"][id$="-order"]`).forEach((el) => {
      const v = parseInt(el.value, 10);
      if (!isNaN(v) && v > max) max = v;
    });

    return max;
  }

  function setOrderForNewRow(row, prefix) {
    const orderInput = row.querySelector(`input[id^="id_${prefix}-"][id$="-order"]`);
    if (!orderInput) return;

    const current = parseInt(orderInput.value, 10);
    if (!current || current === 1) {
      const next = getMaxOrder(prefix) + 1;
      orderInput.value = next;
    }
  }

  function initOrderAutofill() {
    // Handle Django admin formset:added event
    document.body.addEventListener("formset:added", function (event) {
      const row = event.target;          
      const prefix = event.detail?.prefix || 'features';
      setOrderForNewRow(row, prefix);
    });

    // Handle Unfold admin or manual row additions
    const observer = new MutationObserver(function(mutations) {
      mutations.forEach(function(mutation) {
        if (mutation.type === 'childList') {
          mutation.addedNodes.forEach(function(node) {
            if (node.nodeType === 1 && (node.classList.contains('form-row') || node.classList.contains('inline-related'))) {
              // Try to detect the prefix from the input names
              const orderInput = node.querySelector('input[id$="-order"]');
              if (orderInput) {
                const match = orderInput.id.match(/id_(.+?)-\d+-order/);
                const prefix = match ? match[1] : 'features';
                setOrderForNewRow(node, prefix);
              }
            }
          });
        }
      });
    });

    // Observe changes in the inline formset container
    const inlineGroup = document.querySelector('.inline-group, .tabular');
    if (inlineGroup) {
      observer.observe(inlineGroup, { childList: true, subtree: true });
    }
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initOrderAutofill);
  } else {
    initOrderAutofill();
  }
})();
