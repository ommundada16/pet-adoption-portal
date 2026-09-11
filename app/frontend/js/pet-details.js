// pet-details.js - shows one pet's full details and handles the adopt button

// Reads the pet id from the URL, e.g. pet-details.html?id=3
function getPetIdFromUrl() {
    const params = new URLSearchParams(window.location.search);
    return params.get("id");
}

// Fetches one pet's details and displays them on the page
async function loadPetDetails() {
    const petId = getPetIdFromUrl();
    const pet = await apiRequest(`/api/pets/${petId}`, "GET");
    const imageUrl = pet.image_filename
        ? `${API_BASE_URL}/uploads/${pet.image_filename}`
        : "https://via.placeholder.com/300x200?text=No+Image";

    document.getElementById("petDetails").innerHTML = `
        <img src="${imageUrl}">
        <h2>${pet.name}</h2>
        <p><b>Species:</b> ${pet.species}</p>
        <p><b>Breed:</b> ${pet.breed || "Not specified"}</p>
        <p><b>Age:</b> ${pet.age || "Unknown"}</p>
        <p><b>Status:</b> <span class="status-${pet.status}">${pet.status}</span></p>
        <p>${pet.description || ""}</p>
        <button class="btn" id="adoptBtn">Request to Adopt</button>
        <p id="message"></p>
    `;

    document.getElementById("adoptBtn").addEventListener("click", () => requestAdoption(petId));
}

// Sends an adoption request for this pet (must be logged in as an adopter)
async function requestAdoption(petId) {
    if (getRole() !== "user") {
        document.getElementById("message").innerText = "Please login as an adopter to request adoption.";
        return;
    }
    const result = await apiRequest("/api/adoption-requests", "POST", { pet_id: petId }, true);
    document.getElementById("message").innerText = result.message || result.error;
}

renderNavbar();
loadPetDetails();
