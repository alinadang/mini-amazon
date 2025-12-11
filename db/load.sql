\COPY Users(id, email, password, firstname, lastname, address, balance) FROM 'Users.csv' DELIMITER ',' CSV;
SELECT setval(pg_get_serial_sequence('users','id'), COALESCE((SELECT MAX(id) FROM users),0) + 1, false);
\COPY Categories(id, name) FROM 'Categories.csv' DELIMITER ',' CSV;
SELECT setval(pg_get_serial_sequence('categories','id'), COALESCE((SELECT MAX(id) FROM categories),0) + 1, false);
\COPY Products(id, name, description, image_url, price, available, category_id, creator_id) FROM 'Products.csv' DELIMITER ',' CSV;
SELECT setval(pg_get_serial_sequence('products','id'), COALESCE((SELECT MAX(id) FROM products),0) + 1, false);
\COPY Inventory(seller_id, product_id, quantity, seller_price) FROM 'Inventory.csv' DELIMITER ',' CSV;
\COPY CartItems(id, uid, pid, seller_id, quantity, time_added) FROM 'CartItems.csv' DELIMITER ',' CSV 
SELECT setval(pg_get_serial_sequence('cartitems','id'), COALESCE((SELECT MAX(id) FROM cartitems), 0) + 1,false);
\COPY Orders(id, user_id, total_amount, order_date, status) FROM 'Orders.csv' DELIMITER ',' CSV;
SELECT setval(pg_get_serial_sequence('orders', 'id'), COALESCE((SELECT MAX(id) FROM orders), 0) + 1,false);
\COPY OrderItems(id, order_id, product_id, seller_id, quantity, price, fulfillment_status, fulfilled_date) FROM 'OrderItems.csv' WITH (FORMAT csv, DELIMITER ',', NULL '', FORCE_NULL(fulfilled_date));
SELECT setval(pg_get_serial_sequence('orderitems','id'), COALESCE((SELECT MAX(id) FROM orderitems),0) + 1, false);
\COPY Wishes(id, uid, pid, time_added) FROM 'Wishes.csv' DELIMITER ',' CSV;
SELECT setval(pg_get_serial_sequence('wishes','id'), COALESCE((SELECT MAX(id) FROM wishes),0) + 1, false);
\COPY Reviews(review_id, product_id, user_id, rating, comment, date_reviewed) FROM 'Reviews.csv' DELIMITER ',' CSV;
SELECT setval(pg_get_serial_sequence('reviews','review_id'), (SELECT COALESCE(MAX(review_id),0)+1 FROM reviews), false);
\COPY SellerReviews(id, seller_id, user_id, rating, comment, date_reviewed) FROM 'SellerReviews.csv' DELIMITER ',' CSV;
SELECT setval(pg_get_serial_sequence('sellerreviews','id'), (SELECT COALESCE(MAX(id),0)+1 FROM sellerreviews), false);