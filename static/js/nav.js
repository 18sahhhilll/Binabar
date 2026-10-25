/**
 * Binabar: Mobile navigation toggle
 */
(function () {
    'use strict';

    var toggle = document.querySelector('.nav-toggle');
    var navList = document.querySelector('.nav-list');

    if (!toggle || !navList) return;

    toggle.addEventListener('click', function () {
        var expanded = toggle.getAttribute('aria-expanded') === 'true';
        toggle.setAttribute('aria-expanded', String(!expanded));
        navList.classList.toggle('is-open');
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && navList.classList.contains('is-open')) {
            toggle.setAttribute('aria-expanded', 'false');
            navList.classList.remove('is-open');
            toggle.focus();
        }
    });

    document.addEventListener('click', function (e) {
        if (navList.classList.contains('is-open') &&
            !navList.contains(e.target) &&
            !toggle.contains(e.target)) {
            toggle.setAttribute('aria-expanded', 'false');
            navList.classList.remove('is-open');
        }
    });
})();
