(() => {
  'use strict';
  const stop = (event) => { event.preventDefault(); event.stopPropagation(); };
  document.querySelectorAll('[data-inert]').forEach((element) => {
    ['beforeinput', 'input', 'change', 'paste', 'drop'].forEach((type) => element.addEventListener(type, stop));
    element.addEventListener('keydown', (event) => { if (event.key !== 'Tab') stop(event); });
  });
  document.querySelectorAll('form').forEach((form) => form.addEventListener('submit', stop));
  document.querySelectorAll('[data-block-click]').forEach((element) => element.addEventListener('click', stop));
})();
