/**
 * app.js – vanilla JS enhancements for Digi EVM.
 * Everything works with JS disabled (progressive enhancement).
 */

document.addEventListener('DOMContentLoaded', function () {

  /* ---- Mobile nav toggle --------------------------------- */
  const toggle = document.getElementById('navToggle');
  const links  = document.getElementById('navLinks');
  if (toggle && links) {
    toggle.addEventListener('click', function () {
      links.classList.toggle('open');
      toggle.setAttribute('aria-expanded', links.classList.contains('open'));
    });
  }

  /* ---- Auto-dismiss flash messages ----------------------- */
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach(function (el) {
    // Auto-dismiss after 5 seconds
    setTimeout(function () {
      el.style.transition = 'opacity 0.5s';
      el.style.opacity = '0';
      setTimeout(function () { el.remove(); }, 500);
    }, 5000);

    // Manual close button
    const closeBtn = el.querySelector('.flash-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        el.style.transition = 'opacity 0.3s';
        el.style.opacity = '0';
        setTimeout(function () { el.remove(); }, 300);
      });
    }
  });

  /* ---- Confirm dialog on data-confirm buttons/forms ------ */
  document.addEventListener('click', function (e) {
    const btn = e.target.closest('[data-confirm]');
    if (!btn) return;
    const msg = btn.getAttribute('data-confirm');
    if (msg && !window.confirm(msg)) {
      e.preventDefault();
      e.stopImmediatePropagation();
    }
  });

  /* ---- Ballot: require selection before submit ----------- */
  const ballotForm = document.getElementById('ballotForm');
  if (ballotForm) {
    ballotForm.addEventListener('submit', function (e) {
      const selected = ballotForm.querySelector('input[name="candidate_id"]:checked');
      if (!selected) {
        e.preventDefault();
        alert('Please select a candidate or NOTA before submitting.');
        return;
      }
      // data-confirm on the submit button is handled by the global handler above
    });
  }

  /* ---- Password strength indicator ----------------------- */
  const pwInput    = document.getElementById('password');
  const pwStrength = document.getElementById('pw-strength');
  if (pwInput && pwStrength) {
    pwInput.addEventListener('input', function () {
      const val = pwInput.value;
      let score = 0;
      if (val.length >= 8)              score++;
      if (/[A-Za-z]/.test(val))         score++;
      if (/\d/.test(val))               score++;
      if (/[^A-Za-z0-9]/.test(val))     score++;  // bonus: special char

      pwStrength.className = 'pw-strength';
      if (val.length === 0) {
        pwStrength.textContent = '';
      } else if (score <= 1) {
        pwStrength.classList.add('weak');
        pwStrength.textContent = 'Strength: Weak';
      } else if (score === 2 || score === 3) {
        pwStrength.classList.add('medium');
        pwStrength.textContent = 'Strength: Medium';
      } else {
        pwStrength.classList.add('strong');
        pwStrength.textContent = 'Strength: Strong ✓';
      }
    });
  }

  /* ---- Highlight selected candidate card on radio change - */
  const candidateCards = document.querySelectorAll('.candidate-card');
  candidateCards.forEach(function (card) {
    const radio = card.querySelector('input[type="radio"]');
    if (radio) {
      radio.addEventListener('change', function () {
        // The CSS :has(input:checked) handles styling, but we add aria for accessibility
        candidateCards.forEach(function (c) {
          c.setAttribute('aria-selected', 'false');
        });
        card.setAttribute('aria-selected', 'true');
      });
    }
  });

});

