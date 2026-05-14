(function () {
  function applyTheme(name) {
    document.documentElement.classList.add('theme-transition');
    document.documentElement.setAttribute('data-theme', name);
    localStorage.setItem('lv-theme', name);
    setTimeout(function () { document.documentElement.classList.remove('theme-transition'); }, 400);
    updatePickerState(name);
    closeThemePicker();
  }

  function toggleThemePicker() {
    var p = document.getElementById('themePicker');
    if (!p) return;
    if (p.classList.contains('hidden')) {
      p.classList.remove('hidden');
      updatePickerState(document.documentElement.getAttribute('data-theme') || 'geek');
    } else {
      p.classList.add('hidden');
    }
  }

  function closeThemePicker() {
    var p = document.getElementById('themePicker');
    if (p) p.classList.add('hidden');
  }

  function updatePickerState(active) {
    document.querySelectorAll('.theme-option').forEach(function (el) {
      var on = el.dataset.theme === active;
      el.classList.toggle('active', on);
      var c = el.querySelector('.theme-check');
      if (c) {
        c.innerHTML = on
          ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>'
          : '';
      }
    });
  }

  document.addEventListener('click', function (e) {
    if (!e.target.closest('.theme-switcher')) closeThemePicker();
  });

  document.addEventListener('DOMContentLoaded', function () {
    updatePickerState(document.documentElement.getAttribute('data-theme') || 'geek');
  });

  window.applyTheme = applyTheme;
  window.toggleThemePicker = toggleThemePicker;
})();
