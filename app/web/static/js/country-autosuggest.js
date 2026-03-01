let countries = []; // load from /static/data/countries.json

fetch('/static/data/countries.json')
  .then(res => res.json())
  .then(data => countries = data);

document.getElementById('newCityCountry').addEventListener('input', (e) => {
  const value = e.target.value.toLowerCase().trim();
  const list = document.getElementById('countrySuggestions');
  list.innerHTML = '';
  
  if (!value) {
    list.classList.add('is-hidden');
    return;
  }

  const matches = countries.filter(c => c.name.toLowerCase().includes(value));
  matches.forEach(c => {
    const li = document.createElement('li');
    li.textContent = c.name;
    li.onclick = () => {
      e.target.value = c.name;
      list.classList.add('is-hidden');
    };
    list.appendChild(li);
  });

  list.classList.toggle('is-hidden', matches.length === 0);
});
