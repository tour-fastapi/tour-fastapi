console.log('🏨 Hotel autosuggest loaded!');

document.addEventListener('DOMContentLoaded', () => {
  console.log('✅ DOM loaded');
  
  let makkahHotels = [];
  let madinahHotels = [];

  // Fetch both hotel lists
  Promise.all([
    fetch('/static/data/hotels-makkah.json?v=${Date.now()}').then(res => res.json()),
    fetch('/static/data/hotels-madinah.json?v=${Date.now()}').then(res => res.json())
  ]).then(([makkah, madinah]) => {
    makkahHotels = makkah;
    madinahHotels = madinah;
    console.log('✅ Hotels loaded:', makkahHotels.length, 'Makkah,', madinahHotels.length, 'Madinah');
    
    // Hydrate both on edit page
    hydrateHotelFromValue('makkah');
    hydrateHotelFromValue('madinah');
  }).catch(err => {
    console.error('❌ Error loading hotels:', err);
  });

  // Initialize both hotel selectors
  initHotelSelector('makkah', () => makkahHotels);
  initHotelSelector('madinah', () => madinahHotels);

  function initHotelSelector(city, getHotels) {
    const input = document.getElementById(`${city}HotelInputVisible`); // ⚠️ CHANGED
    const list = document.getElementById(`${city}HotelSuggestions`);
    const card = document.getElementById(`${city}HotelCard`);
    const selector = document.getElementById(`${city}HotelSelector`);

    console.log(`🔍 ${city} elements:`, {
      input: input,
      list: list,
      card: card,
      selector: selector
    });

    if (!input) {
      console.error(`❌ Input not found for ${city}`);
      return;
    }

    input.addEventListener('input', () => {
      const value = input.value.toLowerCase().trim();
      console.log(`🔎 Searching ${city}:`, value);
      list.innerHTML = '';

      if (!value) {
        list.classList.add('is-hidden');
        return;
      }

      const matches = getHotels().filter(h =>
        h.name.toLowerCase().includes(value)
      );

      console.log(`✅ Found ${matches.length} matches`);

      matches.forEach(item => {
        const li = document.createElement('li');
        li.innerHTML = `
          <div class="hotel-suggestion-item">
            <strong>${item.name}</strong>
            <span class="hotel-meta">${'★'.repeat(item.stars)} • ${item.distance_km}km • ${item.walking_minutes} min walk</span>
          </div>
        `;
        li.onclick = () => selectHotel(item, city);
        list.appendChild(li);
      });

      list.classList.toggle('is-hidden', matches.length === 0);
    });
  }

  function selectHotel(data, city) {
  console.log(`✅ Selected ${city} hotel:`, data);
    console.log("UID vs ID:", data.uid, data.id);
  
  // ⬇️ CHANGE THIS LINE - use 'prefix' instead of 'fieldName'
  const prefix = city === 'makkah' ? 'mecca' : 'med';
  
  // Update ALL hidden inputs with correct names
  document.getElementById(`${prefix}HotelName`).value = data.name;
  
  document.getElementById(`${prefix}HotelId`).value = data.uid;
  document.getElementById(`${prefix}DistanceKm`).value = data.distance_km;
  document.getElementById(`${prefix}WalkingMinutes`).value = data.walking_minutes;
  document.getElementById(`${prefix}Stars`).value = data.stars;

  // Update card display
  const card = document.getElementById(`${city}HotelCard`);
  card.querySelector('.hotel-name').textContent = data.name;
  card.querySelector('.hotel-stars').textContent = '★'.repeat(data.stars);
  card.querySelector('.hotel-distance').textContent = `${data.distance_km}km from Haram`;
  card.querySelector('.hotel-walking').textContent = `${data.walking_minutes} min walk`;
  
  // Update hotel image with placeholder fallback
  /*
  const hotelImg = card.querySelector('.hotel-image');
  if (hotelImg) {
    
    const actualImagePath = `/media/hotels-in-${city}/${data.id}.jpg`;
    const placeholderPath = 'https://via.placeholder.com/400x300/667eea/ffffff?text=Hotel+Image';
    
    hotelImg.src = actualImagePath;
    hotelImg.alt = data.name;
    hotelImg.onerror = () => {
      hotelImg.src = placeholderPath; // Use placeholder if actual image fails
    };
  }
    */

  // Toggle visibility
  document.getElementById(`${city}HotelSelector`).classList.add('is-hidden');
  card.classList.remove('is-hidden');
}

  function hydrateHotelFromValue(city) {
    const fieldName = city === 'makkah' ? 'mecca_hotel' : 'med_hotel';
    const input = document.querySelector(`input[name="${fieldName}"]`);
    const hotelValue = input?.value?.trim();
    
    console.log(`Hydrating ${city}:`, hotelValue);
    
    if (!hotelValue) return;

    const hotels = city === 'makkah' ? makkahHotels : madinahHotels;
    const match = hotels.find(
      h => h.name.toLowerCase() === hotelValue.toLowerCase()
    );

    if (match) {
      console.log(`✅ Found match for ${city}:`, match);
      selectHotel(match, city);
    } else {
      console.log(`⚠️ No match found for "${hotelValue}" in ${city}`);
    }
  }

  // Edit buttons
  document.getElementById('editMakkahHotel')?.addEventListener('click', () => {
    document.getElementById('makkahHotelCard').classList.add('is-hidden');
    document.getElementById('makkahHotelSelector').classList.remove('is-hidden');
    document.getElementById('makkahHotelInputVisible').focus();
  });

  document.getElementById('editMadinahHotel')?.addEventListener('click', () => {
    document.getElementById('madinahHotelCard').classList.add('is-hidden');
    document.getElementById('madinahHotelSelector').classList.remove('is-hidden');
    document.getElementById('madinahHotelInputVisible').focus();
  });
});