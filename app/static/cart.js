document.addEventListener('DOMContentLoaded', function() {
    // Replace 0 with the dynamic user id as needed
    fetch('/api/cart?user_id=0')
        .then(response => response.json())
        .then(data => {
            const cartDiv = document.getElementById('cart');
            if (cartDiv) {
                cartDiv.innerHTML = '';
                if (data.length === 0) {
                    cartDiv.textContent = 'Cart is empty.';
                } else {
                    data.forEach(item => {
                        const itemElem = document.createElement('div');
                        itemElem.textContent = `Product: ${item.name}, Qty: ${item.quantity}, Price: $${item.price}`;
                        cartDiv.appendChild(itemElem);
                    });
                }
            }
        });
});
