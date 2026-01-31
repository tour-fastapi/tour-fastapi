document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('addAgencyForm');
  if (!form) return;

  const banner = form.querySelector('.form-error-banner');
  const submitBtn = form.querySelector('button[type="submit"]');

  const REQUIRED_SELECTOR = '[data-required]';

  /* ---------------- helpers ---------------- */

  function showError(field) {
    field.classList.add('is-invalid');
    field.setAttribute('aria-invalid', 'true');

    const group = field.closest('.form-group');
    if (!group) return;

    const error = group.querySelector('.form-error');
    if (error) {
      error.classList.remove('is-hidden');
    }
  }

  function clearAllErrors() {
    banner.classList.add('is-hidden');

    form.querySelectorAll('.is-invalid').forEach(el => {
      el.classList.remove('is-invalid');
      el.removeAttribute('aria-invalid');
    });

    form.querySelectorAll('.form-error').forEach(err => {
      err.classList.add('is-hidden');
    });
  }

  function scrollToFirstError() {
    const first = form.querySelector('.is-invalid');
    if (first) {
      first.scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      });
    }
  }

  function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

  /* ---------------- validation ---------------- */

  function validateOnSubmit() {
    let hasErrors = false;

    clearAllErrors();

    const requiredFields = form.querySelectorAll(REQUIRED_SELECTOR);

    requiredFields.forEach(field => {
      const value =
        field.type === 'file'
          ? field.files.length
          : field.value.trim();
          
      // required check
      if (!value) {
        hasErrors = true;
        showError(field);
      }

      // email format check
      if (field.type === 'email' && !isValidEmail(value)) {
        hasErrors = true;
        showError(field);
      }

    });

    if (hasErrors) {
      banner.classList.remove('is-hidden');
      scrollToFirstError();
      return false;
    }

    return true;
  }

  /* ---------------- submit ---------------- */

  form.addEventListener('submit', (e) => {
  if (!validateOnSubmit()) {
    e.preventDefault();
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = 'Saving...';
});
});
