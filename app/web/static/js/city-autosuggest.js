document.addEventListener('DOMContentLoaded', () => {
  let cities = [];

  fetch('/static/data/cities.json')
    .then(res => res.json())
    .then(data => {
      cities = data;
      hydrateCityFromValue(); // ✅ NEW
    });

  const input = document.getElementById('cityInput');
  const list = document.getElementById('citySuggestions');
  const card = document.getElementById('cityCard');
  const selector = document.getElementById('citySelector');

  if (!input) return;

  input.addEventListener('input', () => {
    const value = input.value.toLowerCase().trim();
    list.innerHTML = '';

    if (!value) {
      list.classList.add('is-hidden');
      return;
    }

    const matches = cities.filter(c =>
      c.city.toLowerCase().includes(value)
    );

    matches.forEach(item => {
      const li = document.createElement('li');
      li.textContent = `${item.city}, ${item.country}`;
      li.onclick = () => selectCity(item);
      list.appendChild(li);
      
    });
    // ✅ Add "Add New" option if no matches found
  if (matches.length === 0 && value) {
    console.log("no records found");
    const li = document.createElement('li');
    li.textContent = `Add New "${input.value.trim()}"`;
    li.classList.add('add-new-city');
    li.onclick = () => openAddCityModal(input.value.trim());
    list.appendChild(li);
    list.classList.remove('is-hidden');
  }

    list.classList.toggle('is-hidden', list.children.length === 0);

  });

  window.selectCity = function (data) {
    document.querySelector('input[type="hidden"][name="city"]').value = data.city;
    document.querySelector('[name="country"]').value = data.country;
    document.querySelector('[name="currency_code"]').value = data.currency;

    card.querySelector('.city-name').textContent = data.city;
    card.querySelector('.city-meta').textContent =
      `${data.country} • ${data.currency}`;

    selector.classList.add('is-hidden');
    card.classList.remove('is-hidden');
  }

  // ✅ NEW: hydrate card on edit page
  function hydrateCityFromValue() {
    const cityValue = input.value?.trim();
    if (!cityValue) return; // ✅ add mode — do nothing

    const match = cities.find(
      c => c.city.toLowerCase() === cityValue.toLowerCase()
    );

    if (match) {
      selectCity(match);
    }
  }

  document.getElementById('editCity')?.addEventListener('click', () => {
    card.classList.add('is-hidden');
    selector.classList.remove('is-hidden');
    //input.focus();
  });

  function openAddCityModal(cityName) {
  console.log("Opening Add City Modal for:", cityName);

  const modal = document.getElementById('addCityModal');
  const cityInput = document.getElementById('newCityName');
  const countryInput = document.getElementById('newCityCountry');
  const countryList = document.getElementById('countrySuggestions');

  // Prefill city field
  cityInput.value = cityName;

  // Clear country field and suggestions
  countryInput.value = '';
  countryList.innerHTML = '';
  countryList.classList.add('is-hidden');

  // Show overlay/modal
  modal.style.display = 'flex';               // show overlay
  document.body.classList.add('modal-open');  // lock body scroll

  // Small timeout to allow CSS transition if you have one
  setTimeout(() => {
    modal.classList.add('is-visible');       // optional fade/slide
  }, 10);

  // Focus country input
  countryInput.focus();
}


function closeAddCityModal() {
  const modal = document.getElementById('addCityModal');

  // Trigger fade-out if using CSS transitions
  modal.classList.remove('is-visible');

  setTimeout(() => {
    modal.style.display = 'none';             // hide overlay
    document.body.classList.remove('modal-open'); // unlock scroll

    // Reset fields
    const cityInput = document.getElementById('newCityName');
    const countryInput = document.getElementById('newCityCountry');
    const countryList = document.getElementById('countrySuggestions');

    cityInput.value = '';
    countryInput.value = '';
    countryList.innerHTML = '';
    countryList.classList.add('is-hidden');

    setButtonLoading(false);
  }, 300); // match CSS transition duration
}



});
