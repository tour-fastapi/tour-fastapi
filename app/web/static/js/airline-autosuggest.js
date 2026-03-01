
document.addEventListener('DOMContentLoaded', () => {
  console.log("calling airline autosuggest");
  let airlines = [];

  // Fetch airlines list
  fetch('/static/data/airlines.json')
    .then(res => res.json())
    .then(data => {
      airlines = data;
      console.log('✅ Airlines loaded:', airlines.length);
      
      // Hydrate both fields on edit page
      hydrateAirlineFromValue('onward');
      hydrateAirlineFromValue('return');
      hydrateAirlineFromValue('tentative'); // ✅ add here

    })
    .catch(err => {
      console.error('❌ Error loading airlines:', err);
    });

  // Initialize both airline selectors
  initAirlineSelector('onward', () => airlines);
  initAirlineSelector('return', () => airlines);

  // Initialize tentative selector
initAirlineSelector('tentative', () => airlines);


  function initAirlineSelector(type, getAirlines) {
    const input = document.getElementById(`${type}AirlineInput`);
    const list = document.getElementById(`${type}AirlineSuggestions`);
    const card = document.getElementById(`${type}AirlineCard`);
    const selector = document.getElementById(`${type}AirlineSelector`);

    if (!input) {
      console.log(`⚠️ ${type} airline selector not found`);
      return;
    }

    input.addEventListener('input', () => {
      const value = input.value.toLowerCase().trim();
      list.innerHTML = '';

      if (!value) {
        list.classList.add('is-hidden');
        return;
      }

      // Search by name or IATA code
      const matches = getAirlines().filter(a =>
        a.name.toLowerCase().includes(value) ||
        a.iata.toLowerCase().includes(value)
      );

      console.log(`🔎 Found ${matches.length} airline matches for "${value}"`);

      matches.forEach(item => {
        const li = document.createElement('li');
        li.innerHTML = `
          <div class="airline-suggestion-item">
            <img src="/media/airline-logos/${item.logo}" alt="${item.name}" class="airline-logo-small" onerror="this.style.display='none'">
            <div class="airline-info">
              <strong>${item.name}</strong>
              <span class="airline-code">${item.iata} • ${item.country}</span>
            </div>
          </div>
        `;
        li.onclick = () => selectAirline(item, type);
        list.appendChild(li);
      });

      list.classList.toggle('is-hidden', matches.length === 0);
    });

    input.addEventListener('blur', () => {
      setTimeout(() => list.classList.add('is-hidden'), 150);
    });
  }

  function selectAirline(data, type) {
  console.log(`✅ Selected ${type} airline:`, data);

  // 👉 Persist airline for backend (tentative only)
if (type === 'tentative') {
  document.getElementById('tentative_airline_id').value = data.id;
}

  // Hidden inputs
  document.querySelector(`input[name="${type}_airline"]`).value = data.name;
  document.querySelector(`input[name="${type}_airline_iata"]`).value = data.iata;
  document.querySelector(`input[name="${type}_airline_icao"]`).value = data.icao;

  // Visible input
  const input = document.getElementById(`${type}AirlineInput`);
  if (input) input.value = data.name;

  // Card
  const card = document.getElementById(`${type}AirlineCard`);
  card.querySelector('.airline-name').textContent = data.name;
  card.querySelector('.airline-code-display').textContent = data.iata;
  card.querySelector('.airline-country').textContent = data.country;

  const airlineLogo = card.querySelector('.airline-logo');
  if (airlineLogo) {
    airlineLogo.src = `/media/airline-logos/${data.logo}`;
    airlineLogo.alt = data.name;
    airlineLogo.onerror = () => airlineLogo.style.display = 'none';
  }

  // Hide selector & list
  document.getElementById(`${type}AirlineSelector`).classList.add('is-hidden');
  document.getElementById(`${type}AirlineSuggestions`).classList.add('is-hidden');
  card.classList.remove('is-hidden');
}


  function hydrateAirlineFromValue(type) {
    const input = document.querySelector(`input[name="${type}_airline"]`);
    const airlineValue = input?.value?.trim();
    
    console.log(`Hydrating ${type} airline:`, airlineValue);
    
    if (!airlineValue) return;

    const match = airlines.find(
      a => a.name.toLowerCase() === airlineValue.toLowerCase() ||
           a.iata.toLowerCase() === airlineValue.toLowerCase()
    );

    if (match) {
      console.log(`✅ Found match for ${type}:`, match);
      selectAirline(match, type);
    } else {
      console.log(`⚠️ No match found for "${airlineValue}"`);
    }
  }


  document.addEventListener('click', (e) => {
  document.querySelectorAll('.autosuggest-list').forEach(list => {
    if (!list.parentElement.contains(e.target)) {
      list.classList.add('is-hidden');
    }
  });
});


  // Edit buttons
  document.getElementById('editOnwardAirline')?.addEventListener('click', () => {
    document.getElementById('onwardAirlineCard').classList.add('is-hidden');
    document.getElementById('onwardAirlineSelector').classList.remove('is-hidden');
    //document.getElementById('onwardAirlineInput').focus();
    const input = document.getElementById('onwardAirlineInput');
   input.focus();
    input.select();
  });

  document.getElementById('editReturnAirline')?.addEventListener('click', () => {
    document.getElementById('returnAirlineCard').classList.add('is-hidden');
    document.getElementById('returnAirlineSelector').classList.remove('is-hidden');
    //document.getElementById('returnAirlineInput').focus();
    const input = document.getElementById('returnAirlineInput');
   input.focus();
    input.select();
  });

  document.getElementById('editTentativeAirline')?.addEventListener('click', () => {
  document.getElementById('tentativeAirlineCard').classList.add('is-hidden');
  document.getElementById('tentativeAirlineSelector').classList.remove('is-hidden');

  document.getElementById('tentative_airline_id').value = '';

  const input = document.getElementById('tentativeAirlineInput');
  input.focus();
  input.select();
});


});