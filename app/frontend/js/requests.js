// requests.js - shows the logged-in adopter their own adoption requests

if (getRole() !== "user") {
    window.location.href = "login.html";
}

// Fetches and displays the logged-in user's adoption requests
async function loadMyRequests() {
    const requests = await apiRequest("/api/adoption-requests/my-requests", "GET", null, true);
    const list = document.getElementById("requestsList");
    list.innerHTML = "";
    if (requests.length === 0) {
        list.innerHTML = "<p class='empty-state'>You haven't requested any pets yet.</p>";
        return;
    }
    requests.forEach(r => {
        list.innerHTML += `
            <div class="request-item">
                <p><b>${r.pet_name}</b> (${r.species}) &mdash; <span class="status-${r.status}">${r.status}</span></p>
                <p style="font-size:12px; color:var(--text-light);">Requested on ${new Date(r.request_date).toLocaleDateString()}</p>
            </div>
        `;
    });
}

renderNavbar();
loadMyRequests();
