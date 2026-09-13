// my-pets.js - shelter views, edits, deletes, and uploads photos for its own pets

if (getRole() !== "shelter") {
    window.location.href = "login.html";
}

// Fetches and displays every pet belonging to the logged-in shelter, each as an editable card
async function loadMyPets() {
    const pets = await apiRequest("/api/pets/my-pets", "GET", null, true);
    const list = document.getElementById("myPetsList");
    list.innerHTML = "";
    if (pets.length === 0) {
        list.innerHTML = "<p class='empty-state'>You haven't added any pets yet.</p>";
        return;
    }
    pets.forEach(pet => {
        const imageUrl = pet.image_filename
            ? `${API_BASE_URL}/uploads/${pet.image_filename}`
            : "https://via.placeholder.com/100?text=No+Image";
        list.innerHTML += `
            <div class="request-item" id="pet-${pet.pet_id}">
                <img src="${imageUrl}" style="width:90px; height:90px; object-fit:cover; border-radius:8px; float:left; margin-right:16px;">
                <p><b>Status:</b> <span class="status-${pet.status}">${pet.status}</span></p>

                <div class="form-group">
                    <label>Name</label>
                    <input type="text" id="name-${pet.pet_id}" value="${pet.name}">
                </div>
                <div class="form-group">
                    <label>Species</label>
                    <select id="species-${pet.pet_id}">
                        <option value="Dog" ${pet.species === "Dog" ? "selected" : ""}>Dog</option>
                        <option value="Cat" ${pet.species === "Cat" ? "selected" : ""}>Cat</option>
                        <option value="Rabbit" ${pet.species === "Rabbit" ? "selected" : ""}>Rabbit</option>
                        <option value="Bird" ${pet.species === "Bird" ? "selected" : ""}>Bird</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Breed</label>
                    <input type="text" id="breed-${pet.pet_id}" value="${pet.breed || ''}">
                </div>
                <div class="form-group">
                    <label>Age</label>
                    <input type="number" id="age-${pet.pet_id}" value="${pet.age || ''}">
                </div>
                <div class="form-group">
                    <label>Description</label>
                    <input type="text" id="description-${pet.pet_id}" value="${pet.description || ''}">
                </div>

                <button class="btn-approve" onclick="savePet(${pet.pet_id})">Save Changes</button>
                <button class="btn-reject" onclick="deletePet(${pet.pet_id})">Delete Pet</button>

                <div class="form-group" style="clear:both; margin-top:14px;">
                    <label>Upload / Replace Photo</label>
                    <input type="file" id="image-${pet.pet_id}" accept="image/*">
                    <button class="btn" onclick="uploadPetImage(${pet.pet_id})">Upload</button>
                </div>
                <p id="petMessage-${pet.pet_id}"></p>
            </div>
        `;
    });
}

// Saves the edited fields for one pet
async function savePet(petId) {
    const updates = {
        name: document.getElementById(`name-${petId}`).value,
        species: document.getElementById(`species-${petId}`).value,
        breed: document.getElementById(`breed-${petId}`).value,
        age: document.getElementById(`age-${petId}`).value,
        description: document.getElementById(`description-${petId}`).value
    };
    const result = await apiRequest(`/api/pets/${petId}`, "PUT", updates, true);
    document.getElementById(`petMessage-${petId}`).innerText = result.message || result.error;
}

// Deletes a pet after confirmation, then removes its card from the page
async function deletePet(petId) {
    if (!confirm("Delete this pet? This cannot be undone.")) return;
    await apiRequest(`/api/pets/${petId}`, "DELETE", null, true);
    document.getElementById(`pet-${petId}`).remove();
}

// Uploads (or replaces) a pet's photo - works any time, not just right after adding the pet
async function uploadPetImage(petId) {
    const fileInput = document.getElementById(`image-${petId}`);
    if (!fileInput.files[0]) {
        document.getElementById(`petMessage-${petId}`).innerText = "Choose an image first";
        return;
    }
    const formData = new FormData();
    formData.append("image", fileInput.files[0]);
    const response = await fetch(`${API_BASE_URL}/api/pets/${petId}/upload-image`, {
        method: "POST",
        headers: { "Authorization": "Bearer " + getToken() },
        body: formData
    });
    const result = await response.json();
    if (result.message) {
        loadMyPets();
    } else {
        document.getElementById(`petMessage-${petId}`).innerText = result.error;
    }
}

renderNavbar();
loadMyPets();
