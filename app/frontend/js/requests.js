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
        const cancelBtn = r.status === "Pending"
            ? `<button class="btn-reject" onclick="cancelRequest(${r.request_id})">Cancel Request</button>`
            : "";
        list.innerHTML += `
            <div class="request-item" id="myreq-${r.request_id}">
                <p><b>${r.pet_name}</b> (${r.species}) &mdash; <span class="status-${r.status}">${r.status}</span></p>
                <p style="font-size:12px; color:var(--text-light);">Requested on ${new Date(r.request_date).toLocaleDateString()}</p>
                ${cancelBtn}
            </div>
        `;
    });
}

// Cancels a pending request after confirmation, then removes its card
async function cancelRequest(requestId) {
    if (!confirm("Cancel this adoption request?")) return;
    await apiRequest(`/api/adoption-requests/${requestId}`, "DELETE", null, true);
    document.getElementById(`myreq-${requestId}`).remove();
}

renderNavbar();
loadMyRequests();
