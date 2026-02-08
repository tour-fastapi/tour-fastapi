console.log('📦 Package form JS loaded!');

document.addEventListener('DOMContentLoaded', () => {
  // Toggle between Tentative and Exact dates
  const dateTypeRadios = document.querySelectorAll('input[name="date_type"]');
  const tentativeSection = document.getElementById('tentativeDates');
  const exactSection = document.getElementById('exactDates');

  if (dateTypeRadios.length > 0) {
    dateTypeRadios.forEach(radio => {
      radio.addEventListener('change', (e) => {
        if (e.target.value === 'tentative') {
          tentativeSection.classList.remove('is-hidden');
          exactSection.classList.add('is-hidden');
        } else {
          tentativeSection.classList.add('is-hidden');
          exactSection.classList.remove('is-hidden');
        }
      });
    });
  }


  // ============================================
// INCLUSIONS: Show/hide description fields
// ============================================
const inclusionCheckboxes = document.querySelectorAll('.inclusion-item input[type="checkbox"]');
console.log('🔍 Found checkboxes:', inclusionCheckboxes.length);

inclusionCheckboxes.forEach((checkbox, index) => {
  const item = checkbox.closest('.inclusion-item');
  const descInput = item.querySelector('.inclusion-desc');

  if (descInput) {
    // Initialize on page load
    toggleDescriptionField(checkbox, descInput);

    // Toggle on checkbox change
    checkbox.addEventListener('change', () => {
      console.log('✅ Checkbox changed!', checkbox.checked);
      toggleDescriptionField(checkbox, descInput);
    });
  }
});

function toggleDescriptionField(checkbox, descInput) {
  if (checkbox.checked) {
    descInput.style.display = 'block'; // Show field
    descInput.removeAttribute('disabled');
    console.log('👁️ Showing field');
  } else {
    descInput.style.display = 'none'; // Hide field
    descInput.setAttribute('disabled', 'disabled');
    console.log('🙈 Hiding field');
  }
}

});