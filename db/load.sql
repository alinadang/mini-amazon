-- USERS
\COPY Users(id, email, password, firstname, lastname, address, balance) FROM 'Users.csv' WITH (FORMAT csv, DELIMITER ',', NULL '');
SELECT setval(pg_get_serial_sequence('users','id'), COALESCE((SELECT MAX(id) FROM users),0) + 1, false);

-- CATEGORIES
\COPY Categories(id, name) FROM 'Categories.csv' WITH (FORMAT csv, DELIMITER ',', NULL '');
SELECT setval(pg_get_serial_sequence('categories','id'), COALESCE((SELECT MAX(id) FROM categories),0) + 1, false);

-- PRODUCTS
\COPY Products(id, name, description, image_url, price, available, category_id, creator_id) FROM 'Products.csv' WITH (FORMAT csv, DELIMITER ',', NULL '');
SELECT setval(pg_get_serial_sequence('products','id'), COALESCE((SELECT MAX(id) FROM products),0) + 1, false);

-- INVENTORY
\COPY Inventory(seller_id, product_id, quantity, seller_price) FROM 'Inventory.csv' WITH (FORMAT csv, DELIMITER ',', NULL '');

-- CARTITEMS
\COPY CartItems(id, uid, pid, seller_id, quantity, time_added) FROM 'CartItems.csv' WITH (FORMAT csv, DELIMITER ',', NULL '');
SELECT setval(pg_get_serial_sequence('cartitems','id'), COALESCE((SELECT MAX(id) FROM cartitems),0) + 1, false);

-- ORDERS
\COPY Orders(id, user_id, total_amount, order_date, status) FROM 'Orders.csv' WITH (FORMAT csv, DELIMITER ',', NULL '');
SELECT setval(pg_get_serial_sequence('orders','id'), COALESCE((SELECT MAX(id) FROM orders),0) + 1, false);

-- ORDERITEMS
\COPY OrderItems(id, order_id, product_id, seller_id, quantity, price, fulfillment_status, fulfilled_date) FROM 'OrderItems.csv' WITH (FORMAT csv, DELIMITER ',', NULL '', FORCE_NULL(fulfilled_date));
SELECT setval(pg_get_serial_sequence('orderitems','id'), COALESCE((SELECT MAX(id) FROM orderitems),0) + 1, false);

-- WISHES
\COPY Wishes(id, uid, pid, time_added) FROM 'Wishes.csv' WITH (FORMAT csv, DELIMITER ',', NULL '');
SELECT setval(pg_get_serial_sequence('wishes','id'), COALESCE((SELECT MAX(id) FROM wishes),0) + 1, false);

-- REVIEWS
\COPY Reviews(review_id, product_id, user_id, rating, comment, date_reviewed) FROM 'Reviews.csv' WITH (FORMAT csv, DELIMITER ',', NULL '');
SELECT setval(pg_get_serial_sequence('reviews','review_id'), COALESCE((SELECT MAX(review_id) FROM reviews),0) + 1, false);