// auth.js - handles the login and register form submissions

// Runs when the login form is submitted
document.getElementById("loginForm")?.addEventListener("submit", async function (e) {
    e.preventDefault();
    const role = document.getElementById("role").value;
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    const endpoint = role === "shelter" ? "/api/shelters/login" : "/api/users/login";
    const result = await apiRequest(endpoint, "POST", { email, password });

    if (result.token) {
        saveSession(result.token, role, result.name);
        window.location.href = role === "shelter" ? "admin.html" : "index.html";
    } else {
        document.getElementById("message").innerText = result.error || "Login failed";
    }
});

// Runs when the register form is submitted
document.getElementById("registerForm")?.addEventListener("submit", async function (e) {
    e.preventDefault();
    const role = document.getElementById("role").value;
    const name = document.getElementById("name").value;
    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;
    const phone = document.getElementById("phone").value;
    const address = document.getElementById("address").value;

    const endpoint = role === "shelter" ? "/api/shelters/register" : "/api/users/register";
    const body = role === "shelter" ? { name, email, password, phone, address } : { name, email, password, phone };
    const result = await apiRequest(endpoint, "POST", body);

    if (result.message) {
        document.getElementById("message").innerText = "Registered! You can now log in.";
    } else {
        document.getElementById("message").innerText = result.error || "Registration failed";
    }
});