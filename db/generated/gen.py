from werkzeug.security import generate_password_hash
import csv
from faker import Faker
import random

Faker.seed(0)
fake = Faker()

num_users = 100
num_categories = 10
num_products = 2000
num_inventory = 3000
num_cart_items = 500
num_orders = 400
num_orderitems = 1000
num_wishes = 200
num_reviews = 300
num_seller_reviews = 150

def get_csv_writer(f):
    return csv.writer(f, dialect='unix')

def gen_users(num_users):
    with open('Users.csv', 'w', newline='') as f:
        writer = get_csv_writer(f)
        for uid in range(num_users):
            profile = fake.profile()
            email = profile['mail']
            plain_password = f'pass{uid}'
            password = generate_password_hash(plain_password)
            name_components = profile['name'].split(' ')
            firstname = name_components[0]
            lastname = name_components[-1] if len(name_components) > 1 else ''
            address = fake.address().replace("\n", ", ")
            balance = round(random.uniform(0, 1000), 2)
            writer.writerow([uid, email, password, firstname, lastname, address, balance])

def gen_categories(num_categories):
    with open('Categories.csv', 'w', newline='') as f:
        writer = get_csv_writer(f)
        for i in range(num_categories):
            writer.writerow([i, fake.word().capitalize()])

def gen_products(num_products, num_categories, num_users):
    available_pids = []
    with open('Products.csv', 'w', newline='') as f:
        writer = get_csv_writer(f)
        for pid in range(num_products):
            name = fake.sentence(nb_words=4).replace('.', '')
            description = fake.text(max_nb_chars=100)
            image_url = f'https://picsum.photos/seed/{pid}/800/600'
            price = round(random.uniform(5, 500), 2)
            available = random.choice(['true', 'false'])
            category_id = random.randint(0, num_categories - 1)
            creator_id = random.randint(0, num_users - 1)
            if available == 'true':
                available_pids.append(pid)
            writer.writerow([pid, name, description, image_url, price, available, category_id, creator_id])
    return available_pids

def gen_inventory(num_inventory, num_users, num_products):
    with open('Inventory.csv', 'w', newline='') as f:
        writer = get_csv_writer(f)
        seen = set()
        for _ in range(num_inventory):
            seller_id = random.randint(0, num_users - 1)
            product_id = random.randint(0, num_products - 1)
            if (seller_id, product_id) in seen:
                continue  # avoid duplicate key
            seen.add((seller_id, product_id))
            quantity = random.randint(1, 100)
            seller_price = round(random.uniform(5, 500), 2)
            writer.writerow([seller_id, product_id, quantity, seller_price])

# Guarantee every product is addable: every product has at least one seller w/ stock
def ensure_all_products_in_inventory(num_products):
    products = set(str(pid) for pid in range(num_products))
    present = set()
    rows = []
    with open('Inventory.csv', 'r') as finv:
        reader = csv.reader(finv)
        fieldnames = next(reader)
        for row in reader:
            rows.append(row)
            if int(row[2]) > 0:  # quantity > 0 (col 2)
                present.add(row[1])  # product_id is index 1

    missing = products - present
    for pid in missing:
        # Add seller_id=0, quantity=10, seller_price=9.99 for missing products
        rows.append(['0', pid, '10', '9.99'])

    with open('Inventory.csv', 'w', newline='') as fout:
        writer = csv.writer(fout)
        writer.writerow(fieldnames)
        for row in rows:
            writer.writerow(row)

def gen_cartitems(num_cart_items, num_users, num_products):
    with open('CartItems.csv', 'w', newline='') as f:
        writer = get_csv_writer(f)
        for cid in range(num_cart_items):
            uid = random.randint(0, num_users - 1)
            pid = random.randint(0, num_products - 1)
            seller_id = random.randint(0, num_users - 1)
            quantity = random.randint(1, 5)
            time_added = fake.date_time()
            writer.writerow([cid, uid, pid, seller_id, quantity, time_added])

def gen_orders(num_orders, num_users):
    with open('Orders.csv', 'w', newline='') as f:
        writer = get_csv_writer(f)
        for oid in range(num_orders):
            user_id = random.randint(0, num_users - 1)
            total_amount = round(random.uniform(10, 1000), 2)
            order_date = fake.date_time()
            status = 'cancelled' if random.random() < 0.1 else 'active'
            writer.writerow([oid, user_id, total_amount, order_date, status])

def gen_orderitems(num_orderitems, num_orders, num_products, num_users):
    with open('OrderItems.csv', 'w', newline='') as f:
        writer = get_csv_writer(f)
        for iid in range(num_orderitems):
            order_id = random.randint(0, num_orders - 1)
            product_id = random.randint(0, num_products - 1)
            seller_id = random.randint(0, num_users - 1)
            quantity = random.randint(1, 5)
            price = round(random.uniform(5, 500), 2)
            fulfillment_status = random.choice(['pending', 'fulfilled'])
            fulfilled_date = fake.date_time() if fulfillment_status == 'fulfilled' else None
            writer.writerow([iid, order_id, product_id, seller_id, quantity, price, fulfillment_status, fulfilled_date])

def gen_wishes(num_wishes, num_users, num_products):
    with open('Wishes.csv', 'w', newline='') as f:
        writer = get_csv_writer(f)
        for wid in range(num_wishes):
            uid = random.randint(0, num_users - 1)
            pid = random.randint(0, num_products - 1)
            time_added = fake.date_time()
            writer.writerow([wid, uid, pid, time_added])

def gen_reviews(num_reviews, num_products, num_users):
    with open('Reviews.csv', 'w', newline='') as f:
        writer = get_csv_writer(f)
        seen = set()
        rid = 0
        attempts = 0
        max_attempts = num_reviews * 10  # Prevent infinite loop
        
        while rid < num_reviews and attempts < max_attempts:
            product_id = random.randint(0, num_products - 1)
            user_id = random.randint(0, num_users - 1)
            
            if (product_id, user_id) in seen:
                attempts += 1
                continue  # Skip duplicate pairs
            
            seen.add((product_id, user_id))
            rating = random.randint(1, 5)
            comment = fake.sentence(nb_words=10)
            date_reviewed = fake.date_time()
            writer.writerow([rid, product_id, user_id, rating, comment, date_reviewed])
            rid += 1
            attempts += 1

def gen_seller_reviews(num_seller_reviews, num_users):
    """Generate seller reviews based on actual purchase relationships.
    
    This function:
    1. Reads OrderItems.csv to find buyer-seller relationships
    2. Generates reviews from buyers who have purchased from sellers
    3. Ensures realistic data by only creating reviews where purchases exist
    """
    # Build a mapping of (buyer_id, seller_id) pairs from OrderItems
    buyer_seller_pairs = set()
    try:
        with open('OrderItems.csv', 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                # OrderItems format: [id, order_id, product_id, seller_id, quantity, price, fulfillment_status, fulfilled_date]
                if len(row) >= 4:
                    order_id = row[1]
                    seller_id = row[3]
                    # Now we need to find which user made this order
                    # We'll read Orders.csv to get user_id for this order_id
                    buyer_seller_pairs.add((order_id, seller_id))
    except FileNotFoundError:
        print("Warning: OrderItems.csv not found, generating random seller reviews")
        buyer_seller_pairs = set()
    
    # Map order_id to user_id from Orders.csv
    order_to_user = {}
    try:
        with open('Orders.csv', 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                # Orders format: [id, user_id, total_amount, order_date, status]
                if len(row) >= 2:
                    order_id = row[0]
                    user_id = row[1]
                    order_to_user[order_id] = user_id
    except FileNotFoundError:
        print("Warning: Orders.csv not found")
    
    # Convert to actual (buyer_id, seller_id) pairs
    valid_pairs = []
    for order_id, seller_id in buyer_seller_pairs:
        if order_id in order_to_user:
            buyer_id = order_to_user[order_id]
            # Don't allow self-reviews
            if buyer_id != seller_id:
                valid_pairs.append((buyer_id, seller_id))
    
    # Remove duplicates and convert to list
    valid_pairs = list(set(valid_pairs))
    
    # Generate seller reviews
    with open('SellerReviews.csv', 'w', newline='') as f:
        writer = get_csv_writer(f)
        reviews_generated = 0
        seen_pairs = set()
        
        # If we have valid pairs, use them; otherwise fall back to random
        if valid_pairs:
            for _ in range(num_seller_reviews):
                if not valid_pairs:
                    break
                    
                # Pick a random buyer-seller pair
                buyer_id, seller_id = random.choice(valid_pairs)
                
                # Ensure one review per (buyer, seller) pair
                if (buyer_id, seller_id) in seen_pairs:
                    continue
                    
                seen_pairs.add((buyer_id, seller_id))
                
                rating = random.randint(1, 5)
                comment = fake.sentence(nb_words=random.randint(8, 20))
                date_reviewed = fake.date_time()
                
                # SellerReviews format: [id, seller_id, user_id, rating, comment, date_reviewed]
                writer.writerow([reviews_generated, seller_id, buyer_id, rating, comment, date_reviewed])
                reviews_generated += 1
        else:
            # Fallback: generate random reviews (less realistic but works)
            for rid in range(num_seller_reviews):
                seller_id = random.randint(0, num_users - 1)
                buyer_id = random.randint(0, num_users - 1)
                
                # Don't allow self-reviews
                while buyer_id == seller_id:
                    buyer_id = random.randint(0, num_users - 1)
                
                rating = random.randint(1, 5)
                comment = fake.sentence(nb_words=random.randint(8, 20))
                date_reviewed = fake.date_time()
                
                writer.writerow([rid, seller_id, buyer_id, rating, comment, date_reviewed])

# --- GENERATE ALL TABLES ---
gen_users(num_users)
gen_categories(num_categories)
available_pids = gen_products(num_products, num_categories, num_users)
gen_inventory(num_inventory, num_users, num_products)
ensure_all_products_in_inventory(num_products)
gen_cartitems(num_cart_items, num_users, num_products)
gen_orders(num_orders, num_users)
gen_orderitems(num_orderitems, num_orders, num_products, num_users)
gen_wishes(num_wishes, num_users, num_products)
gen_reviews(num_reviews, num_products, num_users)
gen_seller_reviews(num_seller_reviews, num_users)