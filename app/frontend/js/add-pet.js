// add-pet.js - shelter adds a new pet (photo upload happens afterward on the My Pets page)

if (getRole() !== "shelter") {
    window.location.href = "login.html";
}

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
        window.location.href = "my-pets.html";
    } else {
        document.getElementById("addPetMessage").innerText = result.error || "Failed to add pet";
    }
});

renderNavbar();
