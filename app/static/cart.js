function loadCart() {
    fetch('/api/cart')
        .then(response => {
            if (!response.ok) {
                if (response.status === 401) {
                    document.getElementById('cart').innerHTML =
                        "<div class='alert alert-warning'>You must be logged in to view your cart.</div>";
                } else {
                    document.getElementById('cart').innerHTML =
                        "<div class='alert alert-danger'>An error occurred loading cart.</div>";
                }
                document.getElementById('checkout-btn').disabled = true;
                return [];
            }
            return response.json();
        })
        .then(data => {
            if (!data || !Array.isArray(data)) return;
            const cartDiv = document.getElementById('cart');
            cartDiv.innerHTML = '';
            if (data.length === 0) {
                cartDiv.textContent = 'Cart is empty.';
                document.getElementById('checkout-btn').disabled = true;
                return;
            }
            document.getElementById('checkout-btn').disabled = false;
            data.forEach(item => {
                const itemElem = document.createElement('div');
                itemElem.innerHTML = `
                  Product: ${item.name}, Qty: 
                  <input type="number" value="${item.quantity}" min="1"
                        data-pid="${item.pid}" data-sid="${item.seller_id}" style="width:60px;">
                  Price: $${item.price}
                  <button onclick="removeFromCart(${item.pid}, ${item.seller_id})">Remove</button>
                `;
                cartDiv.appendChild(itemElem);
                // Add robust event listener for updates
                const qtyInput = itemElem.querySelector('input[type="number"]');
                qtyInput.addEventListener('change', function(e) {
                    const pid = this.getAttribute('data-pid');
                    const seller_id = this.getAttribute('data-sid');
                    const quantity = this.value;
                    updateCart(pid, seller_id, quantity);
                });
            });
        });
}

window.updateCart = function(pid, seller_id, quantity) {
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

window.removeFromCart = function(pid, seller_id) {
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

window.checkoutCart = function() {
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
        alert(data.message || (data.success ? "Order placed!" : "Checkout failed"));
        loadCart();
    })
    .catch(err => {
        if (typeof err === "string" && err.startsWith("Not JSON:")) {
        } else {
            alert("Error during checkout: " + err);
        }
    });
};

document.addEventListener('DOMContentLoaded', function() {
    loadCart();
});