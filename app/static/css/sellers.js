document.addEventListener('DOMContentLoaded', function() {
    const sellerId = 0; // replace later

    fetch(`/api/seller_inventory?seller_id=${sellerId}`)
        .then(response => {
            if (!response.ok) throw response;
            return response.json();
        })
        .then(data => {
            const invDiv = document.getElementById('seller-inventory');
            if (!invDiv) return;
            invDiv.innerHTML = '';
            if (!data || data.length === 0) {
                invDiv.textContent = 'No products found for this seller.';
                return;
            }
            data.forEach(item => {
                const itemElem = document.createElement('div');
                const price = item.seller_price !== null ? item.seller_price : item.base_price;
                itemElem.innerHTML = `
                    <strong>${item.name}</strong> — $${Number(price).toFixed(2)}
                    <div>Qty: ${item.quantity} • Available: ${item.available}</div>
                `;
                invDiv.appendChild(itemElem);
            });
        })
        .catch(async err => {
            const invDiv = document.getElementById('seller-inventory');
            const msg = (await err.json().catch(()=>null)) || {error: 'fetch_failed'};
            if (invDiv) invDiv.textContent = 'Error loading inventory: ' + (msg.error || msg.detail || 'unknown');
            console.error('Error fetching seller inventory', msg);
        });
});
