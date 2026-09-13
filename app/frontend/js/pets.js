// pets.js - loads and displays the pet list on the home page

// Fetches pets from the backend, filtered by whatever the species/adoption dropdowns are set to
async function loadPets() {
    const species = document.getElementById("speciesFilter").value;
    const adopted = document.getElementById("adoptedFilter").value;
    const params = new URLSearchParams();
    if (species) params.set("species", species);
    if (adopted) params.set("adopted", adopted);
    const query = params.toString();
    const pets = await apiRequest(query ? `/api/pets?${query}` : "/api/pets", "GET");
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
                <p style="font-size:12px;">Listed by ${pet.shelter_name}</p>
                <a class="view-link" href="pet-details.html?id=${pet.pet_id}">View Details</a>
            </div>
        `;
    });
}

// Runs whenever either filter dropdown is changed
document.getElementById("speciesFilter").addEventListener("change", loadPets);
document.getElementById("adoptedFilter").addEventListener("change", loadPets);

renderNavbar();
loadPets();