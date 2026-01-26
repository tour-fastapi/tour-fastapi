document.addEventListener('DOMContentLoaded', () => {
  let cities = [];

  fetch('/static/data/cities.json')
    .then(res => res.json())
    .then(data => cities = data);

  const input = document.getElementById('cityInput');
  const list = document.getElementById('citySuggestions');
  const card = document.getElementById('cityCard');
  const selector = document.getElementById('citySelector');

  if (!input) return; // safety

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

    list.classList.toggle('is-hidden', matches.length === 0);
  });

  function selectCity(data) {
    document.querySelector('[name="city"]').value = data.city;
    document.querySelector('[name="country"]').value = data.country;
    document.querySelector('[name="currency_code"]').value = data.currency;

    card.querySelector('.city-name').textContent = data.city;
    card.querySelector('.city-meta').textContent =
      `${data.country} • ${data.currency}`;

    selector.classList.add('is-hidden');
    card.classList.remove('is-hidden');
  }

  document.getElementById('editCity').addEventListener('click', () => {
    card.classList.add('is-hidden');
    selector.classList.remove('is-hidden');
    input.focus();
  });
});
