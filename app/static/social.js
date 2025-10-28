document.addEventListener('DOMContentLoaded', () => {
  if (typeof userId === 'undefined') {
    console.error('userId is not defined');
    return;
  }

  const container = document.getElementById('reviews');
  if (!container) return;
  container.textContent = 'Loading…';

  fetch(`/api/feedback?user_id=${encodeURIComponent(userId)}`)
    .then(async (res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .then((rows) => {
      container.innerHTML = '';
      const table = document.createElement('table');
      table.className = 'reviews-table';

      table.innerHTML = `
        <thead>
          <tr>
            <th>Product ID</th>
            <th>Date</th>
            <th>Review</th>
            <th>Stars</th>
          </tr>
        </thead>
        <tbody></tbody>
      `;

      const tbody = table.querySelector('tbody');

      rows.forEach(({ product_id, comment, rating, date_reviewed }) => {
        const tr = document.createElement('tr');

        const tdProduct = document.createElement('td');
        tdProduct.textContent = String(product_id);

        const tdDate = document.createElement('td');
        let dateText = date_reviewed;
        const d = new Date(date_reviewed);
        if (!Number.isNaN(d.getTime())) {
          dateText = d.toLocaleString(undefined, {
            year: 'numeric', month: 'short', day: '2-digit',
            hour: '2-digit', minute: '2-digit'
          });
        }
        tdDate.textContent = dateText;

        const tdReview = document.createElement('td');
        tdReview.textContent = comment; // use textContent to avoid HTML injection

        const tdStars = document.createElement('td');
        const r = Math.max(0, Math.min(5, Number(rating) || 0));
        tdStars.setAttribute('aria-label', `${r} out of 5 stars`);
        tdStars.textContent = '★★★★★'.slice(0, r) + '☆☆☆☆☆'.slice(r);

        tr.append(tdProduct, tdDate, tdReview, tdStars);
        tbody.appendChild(tr);
      });

      container.appendChild(table);
    })
    .catch((err) => {
      console.error(err);
      container.textContent = 'Failed to load reviews.';
    });
});
