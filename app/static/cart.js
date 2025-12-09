let currentSubtotal = 0;
let currentDiscount = 0;

function updateTotalsDisplay() {
    const totalElem = document.getElementById('cart-total');
    const discountText = document.getElementById('cart-discount-text');
    const discountAmt = document.getElementById('cart-discount-amount');
    const finalElem = document.getElementById('cart-final-total');

    if (!totalElem || !finalElem) return;

    totalElem.textContent = `$${currentSubtotal.toFixed(2)}`;
    const finalTotal = Math.max(0, currentSubtotal - currentDiscount);
    finalElem.textContent = `$${finalTotal.toFixed(2)}`;

    if (currentDiscount > 0 && discountText && discountAmt) {
        discountText.style.display = 'inline';
        discountAmt.textContent = `$${currentDiscount.toFixed(2)}`;
    } else if (discountText) {
        discountText.style.display = 'none';
    }
}

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
            const emptyElem = document.getElementById('cart-empty');
            const btn = document.getElementById('checkout-btn');

            if (!tbody || !emptyElem) return;

            tbody.innerHTML = '';
            let total = 0;

            if (data.length === 0) {
                emptyElem.style.display = 'block';
                currentSubtotal = 0;
                currentDiscount = 0;
                updateTotalsDisplay();
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
                      <div class="btn-group btn-group-sm" role="group">
                        <button class="btn btn-outline-secondary"
                                onclick="saveForLater(${item.pid}, ${item.seller_id})">
                          Save
                        </button>
                        <button class="btn btn-outline-danger"
                                onclick="removeFromCart(${item.pid}, ${item.seller_id})">
                          Remove
                        </button>
                      </div>
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

            currentSubtotal = total;
            currentDiscount = 0; // reset discount when cart changes
            updateTotalsDisplay();
        });
}

/* ---------- Saved for later ---------- */

function loadSaved() {
    fetch('/api/cart/saved')
        .then(r => r.ok ? r.json() : [])
        .then(data => {
            const tbody = document.getElementById('saved-table-body');
            const emptyElem = document.getElementById('saved-empty');
            if (!tbody || !emptyElem) return;

            tbody.innerHTML = '';
            if (!data || data.length === 0) {
                emptyElem.style.display = 'block';
                return;
            }
            emptyElem.style.display = 'none';

            data.forEach(item => {
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
                             style="width:48px;height:48px;object-fit:cover;border:1px solid #eee;border-radius:4px;">
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
                             class="form-control form-control-sm text-center"
                             value="${item.quantity}"
                             min="1"
                             disabled>
                    </td>
                    <td>
                      <button class="btn btn-sm btn-outline-primary"
                              onclick="moveToCart(${item.pid}, ${item.seller_id})">
                        Move to Cart
                      </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        });
}

window.saveForLater = function (pid, seller_id) {
    fetch('/api/cart/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid, seller_id, saved: true })
    })
        .then(r => r.json())
        .then(d => {
            if (d.success) {
                loadCart();
                loadSaved();
            } else {
                alert("Failed to save item: " + (d.error || "Unknown error"));
            }
        });
};

window.moveToCart = function (pid, seller_id) {
    fetch('/api/cart/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pid, seller_id, saved: false })
    })
        .then(r => r.json())
        .then(d => {
            if (d.success) {
                loadCart();
                loadSaved();
            } else {
                alert("Failed to move item: " + (d.error || "Unknown error"));
            }
        });
};

/* ---------- Existing cart APIs ---------- */

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
                loadSaved();
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
                loadSaved();
            } else {
                alert("Failed to remove from cart: " + (data.error || "Unknown error"));
            }
        });
};

/* ---------- Coupon: apply button + checkout ---------- */

window.applyCoupon = function () {
    const codeInput = document.getElementById('coupon-code');
    const code = codeInput ? codeInput.value.trim().toUpperCase() : "";

    if (!code) {
        currentDiscount = 0;
        updateTotalsDisplay();
        alert("Enter a coupon code.");
        return;
    }

    if (code === "SAVE10") {
        currentDiscount = Number((currentSubtotal * 0.10).toFixed(2));
        updateTotalsDisplay();
        alert(`Coupon applied: $${currentDiscount.toFixed(2)} off.`);
    } else {
        currentDiscount = 0;
        updateTotalsDisplay();
        alert("Invalid coupon code.");
    }
};

window.checkoutCart = function () {
    const codeInput = document.getElementById('coupon-code');
    const coupon = codeInput ? codeInput.value.trim() : "";

    fetch('/api/cart/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ coupon })
    })
        .then(response => {
            const contentType = response.headers.get("content-type");
            if (!contentType || !contentType.includes("application/json")) {
                alert("You must be logged in to checkout.");
                loadCart();
                loadSaved();
                return Promise.reject("Not JSON: " + response.status);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                let msg = data.message || "Order placed!";
                if (typeof data.discount !== "undefined" && Number(data.discount) > 0) {
                    msg += ` Discount applied: $${Number(data.discount).toFixed(2)}.`;
                }
                if (typeof data.new_balance !== "undefined") {
                    msg += ` New balance: $${Number(data.new_balance).toFixed(2)}.`;
                }
                alert(msg);
            } else {
                alert(data.message || "Checkout failed");
            }
            loadCart();
            loadSaved();
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
    loadSaved();
});