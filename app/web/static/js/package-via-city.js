  // Track which via field opened the modal (onward/return)
  window.__viaCityContext = { prefix: null };

  // When modal saves a city, it usually calls selectCity(newCity)
  // We'll handle that here for package via-city too.
  window.selectCity = function (newCity) {
    try {
      const prefix = window.__viaCityContext?.prefix;
      if (!prefix || !newCity || !newCity.city) {
        console.warn("⚠️ selectCity called but missing context/city", { prefix, newCity });
        return;
      }

      const input = document.getElementById(`${prefix}ViaInput`);
      const hidden = document.querySelector(`input[name="${prefix}_via"]`);
      const list = document.getElementById(`${prefix}ViaSuggestions`);

      if (hidden) hidden.value = newCity.city;  // store only city name
      if (input) input.value = newCity.city;
      if (list) list.classList.add("is-hidden");

      // Update local cities array so autosuggest includes it immediately
      // if (Array.isArray(cities)) {
      //   cities.push(newCity);
      // }

      // Clear context after selection
      window.__viaCityContext.prefix = null;

      console.log(`✅ Via city selected for ${prefix}:`, newCity.city);
    } catch (e) {
      console.error("❌ selectCity handler failed:", e);
    }
  };


// ----------------------------------------------------
// Minimal Add City Modal helpers (for package page)
// ----------------------------------------------------
window.openAddCityModal = function (cityName = "") {
  const modal = document.getElementById("addCityModal");
  const cityInput = document.getElementById("newCityName");

  if (!modal || !cityInput) {
    console.error("❌ Add City modal markup not found on this page");
    return;
  }

  cityInput.value = cityName || "";

  modal.style.display = "flex";
  document.body.classList.add("modal-open");
  setTimeout(() => modal.classList.add("is-visible"), 10);
};

window.closeAddCityModal = function () {
  const modal = document.getElementById("addCityModal");
  if (!modal) return;

  modal.classList.remove("is-visible");
  setTimeout(() => {
    modal.style.display = "none";
    document.body.classList.remove("modal-open");
  }, 200);
};


document.addEventListener("DOMContentLoaded", () => {

  if (typeof window.openAddCityModal !== "function") {
  window.openAddCityModal = function (cityName) {
    const modal = document.getElementById("addCityModal");
    const cityInput = document.getElementById("newCityName");

    if (!modal || !cityInput) {
      console.error("❌ Add City modal markup not found on this page");
      return;
    }

    cityInput.value = cityName || "";
    modal.style.display = "flex";
    document.body.classList.add("modal-open");
    setTimeout(() => modal.classList.add("is-visible"), 10);
  };
}


  let cities = [];

  fetch("/static/data/cities.json")
    .then((res) => res.json())
    .then((data) => {
      cities = data || [];
      initViaCity("onward");
      initViaCity("return");

      // hydrate on edit page if hidden value already exists
      hydrateViaCity("onward");
      hydrateViaCity("return");
    })
    .catch((err) => console.error("❌ Error loading cities:", err));

  function initViaCity(prefix) {
    const input = document.getElementById(`${prefix}ViaInput`);
    const list = document.getElementById(`${prefix}ViaSuggestions`);
    const hidden = document.querySelector(`input[name="${prefix}_via"]`);

    if (!input || !list || !hidden) {
      console.log(`⚠️ Via autosuggest not found for: ${prefix}`);
      return;
    }

    input.addEventListener("input", () => {
      const value = input.value.toLowerCase().trim();
      list.innerHTML = "";

      if (!value) {
        list.classList.add("is-hidden");
        return;
      }

      const matches = cities.filter((c) =>
        (c.city || "").toLowerCase().includes(value)
      );

      matches.slice(0, 10).forEach((item) => {
        const li = document.createElement("li");
        li.textContent = `${item.city}, ${item.country}`;
        li.onclick = () => {
          hidden.value = item.city;   // ✅ only store city name
          input.value = item.city;    // ✅ show selected city
          list.classList.add("is-hidden");
        };
        list.appendChild(li);
      });

      // ✅ Add New option (same behavior as agency form)
      if (matches.length === 0 && value) {
        const li = document.createElement("li");
        li.textContent = `Add New "${input.value.trim()}"`;
        li.classList.add("add-new-city");
        li.onclick = () => {
          const name = input.value.trim();
          if (!name) return;

          // Remember which field opened the modal
          window.__viaCityContext.prefix = prefix;

          if (typeof window.openAddCityModal === "function") {
            window.openAddCityModal(name);
          } else {
            console.error("❌ openAddCityModal not found on this page");
          }
        };
        list.appendChild(li);
      }

      list.classList.toggle("is-hidden", list.children.length === 0);
    });

    // click outside closes list
    document.addEventListener("click", (e) => {
      if (!list.parentElement.contains(e.target)) {
        list.classList.add("is-hidden");
      }
    });
  }

  

  function hydrateViaCity(prefix) {
    const input = document.getElementById(`${prefix}ViaInput`);
    const hidden = document.querySelector(`input[name="${prefix}_via"]`);
    const field = document.getElementById(`${prefix}ViaField`);

    if (!input || !hidden) return;

    const saved = (hidden.value || "").trim();
    if (!saved) return;

    input.value = saved;

    // ✅ ensure Via field is visible if saved value exists
    if (field) field.style.display = "";
  }

});
