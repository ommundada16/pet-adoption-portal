// pets.js - loads and displays the pet list on the home page

// Builds the navbar links based on whether someone is logged in, and as what role
function renderNavbar() {
    const role = getRole();
    const navbar = document.getElementById("navbar");
    if (role === "user") {
        navbar.innerHTML = `<a href="index.html">Browse Pets</a> <a href="my-requests.html">My Requests</a> <a href="#" onclick="logout()">Logout</a>`;
    } else if (role === "shelter") {
        navbar.innerHTML = `<a href="index.html">Browse Pets</a> <a href="admin.html">Admin Dashboard</a> <a href="#" onclick="logout()">Logout</a>`;
    } else {
        navbar.innerHTML = `<a href="index.html">Browse Pets</a> <a href="login.html">Login</a> <a href="register.html">Register</a>`;
    }
}

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
                <p>${pet.species} - ${pet.status}</p>
                <a href="pet-details.html?id=${pet.pet_id}">View Details</a>
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