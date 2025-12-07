\COPY Users(id, email, password, firstname, lastname, address, balance) FROM 'Users.csv' DELIMITER ',' CSV;
\COPY Categories(id, name) FROM 'Categories.csv' DELIMITER ',' CSV;
\COPY Products(id, name, description, image_url, price, available, category_id) FROM 'Products.csv' DELIMITER ',' CSV;
\COPY Inventory(seller_id, product_id, quantity, seller_price) FROM 'Inventory.csv' DELIMITER ',' CSV;
\COPY CartItems(id, uid, pid, seller_id, quantity, time_added) FROM 'CartItems.csv' DELIMITER ',' CSV;
\COPY Orders(id, user_id, total_amount, order_date, status) FROM 'Orders.csv' DELIMITER ',' CSV;
\COPY OrderItems(id, order_id, product_id, seller_id, quantity, price, fulfillment_status, fulfilled_date) FROM 'OrderItems.csv' DELIMITER ',' CSV;
\COPY Wishes(id, uid, pid, time_added) FROM 'Wishes.csv' DELIMITER ',' CSV;
\COPY Reviews(review_id, product_id, user_id, rating, comment, date_reviewed) FROM 'Reviews.csv' DELIMITER ',' CSV;

                         
