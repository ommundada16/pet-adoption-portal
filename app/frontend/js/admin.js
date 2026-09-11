// admin.js - shelter dashboard: view and respond to adoption requests

if (getRole() !== "shelter") {
    window.location.href = "login.html";
}

// Fetches and displays pending adoption requests made for this shelter's pets
async function loadShelterRequests() {
    const requests = await apiRequest("/api/adoption-requests/shelter-requests", "GET", null, true);
    const list = document.getElementById("requestsList");
    list.innerHTML = "";
    if (requests.length === 0) {
        list.innerHTML = "<p class='empty-state'>No pending adoption requests.</p>";
        return;
    }
    requests.forEach(r => {
        list.innerHTML += `
            <div class="request-item" id="request-${r.request_id}">
                <p><b>${r.pet_name}</b> requested by ${r.user_name} &mdash; <span class="status-${r.status}">${r.status}</span></p>
                <button class="btn-approve" onclick="respondToRequest(${r.request_id}, 'Approved', this)">Approve</button>
                <button class="btn-reject" onclick="respondToRequest(${r.request_id}, 'Rejected', this)">Reject</button>
            </div>
        `;
    });
}

// Approves or rejects one request, then removes its card immediately so it can't be actioned twice
async function respondToRequest(requestId, status, buttonEl) {
    const card = document.getElementById(`request-${requestId}`);
    card.querySelectorAll("button").forEach(btn => btn.disabled = true);

    await apiRequest(`/api/adoption-requests/${requestId}`, "PUT", { status }, true);
    card.remove();

    const list = document.getElementById("requestsList");
    if (!list.querySelector(".request-item")) {
        list.innerHTML = "<p class='empty-state'>No pending adoption requests.</p>";
    }
}

renderNavbar();
loadShelterRequests();
