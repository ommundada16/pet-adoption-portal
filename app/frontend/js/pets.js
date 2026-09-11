// pets.js - loads and displays the pet list on the home page

// Fetches pets from the backend, optionally filtered by species
async function loadPets(species = "") {
    const endpoint = species ? `/api/pets?species=${species}` : "/api/pets";
    const pets = await apiRequest(endpoint, "GET");
    displayPets(pets);
}

// Turns the list of pets into HTML cards on the page
function displayPets(pets) {
    const petList = document.getElementById("petList");
    petList.innerHTML = "";
    pets.forEach(pet => {
        const imageUrl = pet.image_filename
            ? `${API_BASE_URL}/uploads/${pet.image_filename}`
            : "https://via.placeholder.com/200x150?text=No+Image";
        petList.innerHTML += `
            <div class="pet-card">
                <img src="${imageUrl}" alt="${pet.name}">
                <h3>${pet.name}</h3>
                <p>${pet.species} &mdash; <span class="status-${pet.status}">${pet.status}</span></p>
                <a class="view-link" href="pet-details.html?id=${pet.pet_id}">View Details</a>
            </div>
        `;
    });
}

// Runs whenever the species dropdown is changed
document.getElementById("speciesFilter").addEventListener("change", function () {
    loadPets(this.value);
});

renderNavbar();
loadPets();