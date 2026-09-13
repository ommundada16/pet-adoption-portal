// api.js - shared helper functions for talking to the backend

// Builds the backend's address from whatever host the page was loaded from
// (works on localhost during development AND on the GCP VM's public IP after deployment)
const API_BASE_URL = `${window.location.protocol}//${window.location.hostname}:5000`;

// Saves login info in the browser after a successful login
function saveSession(token, role, name) {
    localStorage.setItem("token", token);
    localStorage.setItem("role", role);
    localStorage.setItem("name", name);
}

// Reads the saved login token
function getToken() {
    return localStorage.getItem("token");
}

// Reads the saved role (user or shelter)
function getRole() {
    return localStorage.getItem("role");
}

// Clears the saved login and sends the browser back to the login page
function logout() {
    localStorage.clear();
    window.location.href = "login.html";
}

// One reusable function for every API call the frontend makes
async function apiRequest(endpoint, method = "GET", body = null, useAuth = false) {
    const headers = { "Content-Type": "application/json" };
    if (useAuth) {
        headers["Authorization"] = "Bearer " + getToken();
    }
    const response = await fetch(API_BASE_URL + endpoint, {
        method: method,
        headers: headers,
        body: body ? JSON.stringify(body) : null
    });
    return response.json();
}

// Builds the navbar links based on whether someone is logged in, and as what role
function renderNavbar() {
    const role = getRole();
    const navLinks = document.getElementById("navLinks");
    if (role === "user") {
        navLinks.innerHTML = `<a href="index.html">Browse Pets</a> <a href="my-requests.html">My Requests</a> <a href="#" onclick="logout()">Logout</a>`;
    } else if (role === "shelter") {
        navLinks.innerHTML = `<a href="index.html">Browse Pets</a> <a href="admin.html">Requests</a> <a href="my-pets.html">My Pets</a> <a href="add-pet.html">Add New Pet</a> <a href="#" onclick="logout()">Logout</a>`;
    } else {
        navLinks.innerHTML = `<a href="index.html">Browse Pets</a> <a href="login.html">Login</a> <a href="register.html">Register</a>`;
    }
}