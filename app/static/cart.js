function loadCart() {
    fetch('/api/cart')
        .then(response => {
            if (!response.ok) {
                const cartDiv = document.getElementById('cart-body');
                if (!cartDiv) return;
                if (response.status === 401) {
                    cartDiv.innerHTML =
                        "<div class='alert alert-warning mb-0'>You must be logged in to view your cart.</div>";
                } else {
                    cartDiv.innerHTML =
                        "<div class='alert alert-danger mb-0'>An error occurred loading cart.</div>";
                }
                const btn = document.getElementById('checkout-btn');
                if (btn) btn.disabled = true;
                return [];
            }
            return response.json();
        })
        .then(data => {
            if (!data || !Array.isArray(data)) return;

            const tbody = document.getElementById('cart-table-body');
            const totalElem = document.getElementById('cart-total');
            const emptyElem = document.getElementById('cart-empty');
            const btn = document.getElementById('checkout-btn');

            if (!tbody || !totalElem || !emptyElem) return;

            tbody.innerHTML = '';
            let total = 0;

            if (data.length === 0) {
                emptyElem.style.display = 'block';
                totalElem.textContent = '$0.00';
                if (btn) btn.disabled = true;
                return;
            }

            emptyElem.style.display = 'none';
            if (btn) btn.disabled = false;

            data.forEach(item => {
                const lineTotal = Number(item.price) * Number(item.quantity || 0);
                total += lineTotal;

                const imgSrc = (item.image_url && item.image_url.trim())
                    ? item.image_url
                    : `https://picsum.photos/seed/${item.pid}/80/80`;

                const productUrl = `/product/${item.pid}`;

                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>
                      <div class="d-flex align-items-center">
                        <img src="${imgSrc}"
                             alt="${item.name}"
                             class="me-2"
                             style="width:64px;height:64px;object-fit:cover;border:1px solid #eee;border-radius:4px;">
                        <div>
                          <a href="${productUrl}" class="fw-semibold text-decoration-none">
                            ${item.name}
                          </a><br>
                          <small class="text-muted">Product ID: ${item.pid}</small>
                        </div>
                      </div>
                    </td>
                    <td>${item.seller_id}</td>
                    <td>$${Number(item.price).toFixed(2)}</td>
                    <td style="width:110px;">
                      <input type="number"
                             class="form-control form-control-sm text-center cart-qty-input"
                             value="${item.quantity}"
                             min="1"
                             data-pid="${item.pid}"
                             data-sid="${item.seller_id}">
                    </td>
                    <td>$${lineTotal.toFixed(2)}</td>
                    <td>
                      <button class="btn btn-sm btn-outline-danger"
                              onclick="removeFromCart(${item.pid}, ${item.seller_id})">
                        Remove
                      </button>
                    </td>
                `;
                tbody.appendChild(tr);

                const qtyInput = tr.querySelector('.cart-qty-input');
                qtyInput.addEventListener('change', function () {
                    const pid = this.getAttribute('data-pid');
                    const seller_id = this.getAttribute('data-sid');
                    const quantity = this.value;
                    if (Number(quantity) < 1) {
                        this.value = 1;
                    }
                    updateCart(pid, seller_id, this.value);
                });
            });

            totalElem.textContent = `$${total.toFixed(2)}`;
        });
}

window.updateCart = function (pid, seller_id, quantity) {
    fetch('/api/cart/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid, seller_id, quantity: Number(quantity) })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                loadCart();
            } else {
                alert("Failed to update cart: " + (data.error || "Unknown error"));
            }
        });
};

window.removeFromCart = function (pid, seller_id) {
    fetch('/api/cart/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid, seller_id })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                loadCart();
            } else {
                alert("Failed to remove from cart: " + (data.error || "Unknown error"));
            }
        });
};

window.checkoutCart = function () {
    fetch('/api/cart/checkout', {
        method: 'POST'
    })
        .then(response => {
            const contentType = response.headers.get("content-type");
            if (!contentType || !contentType.includes("application/json")) {
                alert("You must be logged in to checkout.");
                loadCart();
                return Promise.reject("Not JSON: " + response.status);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                const extra = typeof data.new_balance !== "undefined"
                    ? ` New balance: $${Number(data.new_balance).toFixed(2)}`
                    : "";
                alert((data.message || "Order placed!") + extra);
            } else {
                alert(data.message || "Checkout failed");
            }
            loadCart();
        })
        .catch(err => {
            if (typeof err === "string" && err.startsWith("Not JSON:")) {
                // handled above
            } else {
                alert("Error during checkout: " + err);
            }
        });
};

document.addEventListener('DOMContentLoaded', function () {
    loadCart();
});