document.addEventListener('DOMContentLoaded', function() {
    const el = document.getElementById('seller-inventory');
    let sellerId = 1;
    if (el && el.dataset && el.dataset.sellerId) {
        sellerId = Number(el.dataset.sellerId);
    } else {
        console.warn('seller-inventory element not found or missing seller-id; using sellerId=1');
    }

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
                const price = item.seller_price !== null ? item.seller_price : item.base_price;
                const itemElem = document.createElement('div');
                itemElem.className = 'seller-item';
                itemElem.innerHTML = `
                    <h4>${item.name} <small>#${item.id}</small></h4>
                    <div>Price: $${Number(price).toFixed(2)}</div>
                    <div>Qty: ${item.quantity} • Available: ${item.available ? 'Yes' : 'No'}</div>
                `;
                invDiv.appendChild(itemElem);
            });
        })
        .catch(async err => {
            const invDiv = document.getElementById('seller-inventory');
            let msg = 'unknown';
            try {
                const body = await err.json();
                msg = body.error || body.detail || JSON.stringify(body);
            } catch (e) {
                msg = 'fetch failed';
            }
            if (invDiv) invDiv.textContent = 'Error loading inventory: ' + msg;
            console.error('Error fetching seller inventory', err);
        });
});
