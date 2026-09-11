// add-pet.js - shelter adds a new pet and uploads its photo

if (getRole() !== "shelter") {
    window.location.href = "login.html";
}

let newPetId = null;

// Runs when the "Add New Pet" form is submitted
document.getElementById("addPetForm").addEventListener("submit", async function (e) {
    e.preventDefault();
    const pet = {
        name: document.getElementById("petName").value,
        species: document.getElementById("petSpecies").value,
        breed: document.getElementById("petBreed").value,
        age: document.getElementById("petAge").value,
        description: document.getElementById("petDescription").value
    };
    const result = await apiRequest("/api/pets", "POST", pet, true);
    if (result.pet_id) {
        newPetId = result.pet_id;
        document.getElementById("addPetMessage").innerText = "Pet added! Now upload a photo below.";
        document.getElementById("uploadSection").style.display = "block";
    } else {
        document.getElementById("addPetMessage").innerText = result.error || "Failed to add pet";
    }
});

// Runs when "Upload" is clicked - sends the image as multipart form data (not JSON)
document.getElementById("uploadBtn").addEventListener("click", async function () {
    const fileInput = document.getElementById("petImage");
    if (!fileInput.files[0]) {
        document.getElementById("uploadMessage").innerText = "Choose an image first";
        return;
    }
    const formData = new FormData();
    formData.append("image", fileInput.files[0]);

    const response = await fetch(`${API_BASE_URL}/api/pets/${newPetId}/upload-image`, {
        method: "POST",
        headers: { "Authorization": "Bearer " + getToken() },
        body: formData
    });
    const result = await response.json();
    document.getElementById("uploadMessage").innerText = result.message || result.error;
});

renderNavbar();
