from flask import Flask, request, jsonify
from flask_cors import CORS
import pyodbc
from pyodbc import Error
import hashlib
import jwt
import datetime
from flask import Flask, send_from_directory
import os

app = Flask(__name__)
CORS(app) # Mengizinkan CORS untuk frontend
app.config['SECRET_KEY'] = 'your_secret_key_farhan_shop' # Ganti dengan kunci rahasia yang kuat

# Konfigurasi Database SQL Server untuk Windows Authentication
DB_CONFIG = {
    'server': 'LAPTOP-DU6E16BV', # Ganti dengan nama server SQL Server Anda
    'database': 'FarhanShopDB', # Ganti dengan nama database Anda
    'driver': '{ODBC Driver 17 for SQL Server}' # Sesuaikan dengan driver ODBC yang terinstal
    # Tidak perlu 'username' dan 'password' karena menggunakan Windows Authentication
}

def get_db_connection():
    """
    Mendapatkan koneksi database SQL Server menggunakan Windows Authentication.
    """
    try:
        conn_str = (
            f"DRIVER={DB_CONFIG['driver']};"
            f"SERVER={DB_CONFIG['server']};"
            f"DATABASE={DB_CONFIG['database']};"
            f"Trusted_Connection=yes;" # Menggunakan Windows Authentication
        )
        conn = pyodbc.connect(conn_str)
        return conn
    except Error as e:
        print(f"Error connecting to SQL Server: {e}")
        return None

def execute_query(query, params=None, fetch=False):
    """
    Menjalankan query SQL dan mengembalikan hasil jika fetch=True.
    """
    conn = get_db_connection()
    if conn is None:
        return None

    cursor = conn.cursor()
    try:
        cursor.execute(query, params or ())
        if fetch:
            columns = [column[0] for column in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            return results
        else:
            conn.commit()
            return True
    except Error as e:
        print(f"Database Error: {e}")
        conn.rollback() # Rollback transaksi jika ada kesalahan
        return None
    finally:
        cursor.close()
        conn.close()

def hash_password(password):
    """
    Menghash password menggunakan SHA256.
    """
    return hashlib.sha256(password.encode()).hexdigest()

@app.route('/')
def home():
    return "Selamat datang di API Farhan Shop (SQL Server Windows Auth)!"

@app.route('/register', methods=['POST'])
def register():
    """
    Endpoint untuk registrasi user baru.
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')

    if not username or not password or not email:
        return jsonify({'message': 'Username, password, dan email harus diisi'}), 400

    hashed_password = hash_password(password)

    user_exists = execute_query("SELECT id FROM users WHERE username = ? OR email = ?", (username, email), fetch=True)
    if user_exists:
        return jsonify({'message': 'Username atau email sudah terdaftar'}), 409

    query = "INSERT INTO users (username, password, email) VALUES (?, ?, ?)"
    if execute_query(query, (username, hashed_password, email)):
        return jsonify({'message': 'Registrasi berhasil!'}), 201
    return jsonify({'message': 'Registrasi gagal'}), 500

@app.route('/login', methods=['POST'])
def login():
    """
    Endpoint untuk login user.
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username dan password harus diisi'}), 400

    query = "SELECT id, username, password FROM users WHERE username = ?"
    user = execute_query(query, (username,), fetch=True)

    if user and len(user) > 0:
        user = user[0]
        if user['password'] == hash_password(password):
            token = jwt.encode({
                'user_id': user['id'],
                'username': user['username'],
                'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
            }, app.config['SECRET_KEY'], algorithm='HS256')
            return jsonify({'message': 'Login berhasil!', 'token': token, 'username': user['username']}), 200
    return jsonify({'message': 'Username atau password salah'}), 401

@app.route('/products', methods=['GET'])
def get_products():
    """
    Endpoint untuk mendapatkan daftar produk.
    """
    query = "SELECT id, name, description, price, original_price, discount, image_url, stock FROM products"
    products = execute_query(query, fetch=True)
    if products is not None:
        return jsonify(products), 200
    return jsonify({'message': 'Gagal mengambil produk'}), 500

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    """
    Endpoint untuk menambahkan produk ke keranjang user.
    Membutuhkan autentikasi token JWT.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'message': 'Token tidak tersedia'}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = decoded_token['user_id']
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token kadaluarsa'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Token tidak valid'}), 401

    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)

    if not product_id or quantity < 1:
        return jsonify({'message': 'ID produk dan kuantitas tidak valid'}), 400

    product = execute_query("SELECT id, stock FROM products WHERE id = ?", (product_id,), fetch=True)
    if not product or product[0]['stock'] < quantity:
        return jsonify({'message': 'Produk tidak ditemukan atau stok tidak cukup'}), 404

    cart_item = execute_query("SELECT id, quantity FROM carts WHERE user_id = ? AND product_id = ?", (user_id, product_id), fetch=True)

    if cart_item:
        new_quantity = cart_item[0]['quantity'] + quantity
        execute_query("UPDATE carts SET quantity = ? WHERE id = ?", (new_quantity, cart_item[0]['id']))
        return jsonify({'message': 'Kuantitas produk di keranjang diperbarui'}), 200
    else:
        query = "INSERT INTO carts (user_id, product_id, quantity) VALUES (?, ?, ?)"
        if execute_query(query, (user_id, product_id, quantity)):
            return jsonify({'message': 'Produk ditambahkan ke keranjang'}), 201
    return jsonify({'message': 'Gagal menambahkan produk ke keranjang'}), 500


@app.route('/cart', methods=['GET'])
def get_cart():
    """
    Endpoint untuk mendapatkan item di keranjang user.
    Membutuhkan autentikasi token JWT.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'message': 'Token tidak tersedia'}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = decoded_token['user_id']
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token kadaluarsa'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Token tidak valid'}), 401

    query = """
    SELECT c.product_id AS id, p.name, p.price, p.image_url, c.quantity
    FROM carts c
    JOIN products p ON c.product_id = p.id
    WHERE c.user_id = ?
    """
    cart_items = execute_query(query, (user_id,), fetch=True)
    if cart_items is not None:
        return jsonify(cart_items), 200
    return jsonify({'message': 'Gagal mengambil item keranjang'}), 500

@app.route('/update_cart_quantity', methods=['POST'])
def update_cart_quantity():
    """
    Endpoint untuk memperbarui kuantitas item di keranjang.
    Membutuhkan autentikasi token JWT.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'message': 'Token tidak tersedia'}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = decoded_token['user_id']
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token kadaluarsa'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Token tidak valid'}), 401

    data = request.get_json()
    product_id = data.get('product_id')
    quantity = data.get('quantity')

    if not product_id or quantity is None or quantity < 0:
        return jsonify({'message': 'ID produk dan kuantitas tidak valid'}), 400

    if quantity == 0:
        query = "DELETE FROM carts WHERE user_id = ? AND product_id = ?"
        if execute_query(query, (user_id, product_id)):
            return jsonify({'message': 'Item dihapus dari keranjang'}), 200
        return jsonify({'message': 'Gagal menghapus item dari keranjang'}), 500
    else:
        query = "UPDATE carts SET quantity = ? WHERE user_id = ? AND product_id = ?"
        if execute_query(query, (quantity, user_id, product_id)):
            return jsonify({'message': 'Kuantitas keranjang diperbarui'}), 200
        return jsonify({'message': 'Gagal memperbarui kuantitas keranjang'}), 500

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    """
    Endpoint untuk menghapus item dari keranjang.
    Membutuhkan autentikasi token JWT.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'message': 'Token tidak tersedia'}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = decoded_token['user_id']
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token kadaluarsa'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Token tidak valid'}), 401

    data = request.get_json()
    product_id = data.get('product_id')

    if not product_id:
        return jsonify({'message': 'ID produk tidak valid'}), 400

    query = "DELETE FROM carts WHERE user_id = ? AND product_id = ?"
    if execute_query(query, (user_id, product_id)):
        return jsonify({'message': 'Item berhasil dihapus dari keranjang'}), 200
    return jsonify({'message': 'Gagal menghapus item dari keranjang'}), 500

@app.route('/place_order', methods=['POST'])
def place_order():
    """
    Endpoint untuk menempatkan pesanan dari keranjang.
    Membutuhkan autentikasi token JWT.
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'message': 'Token tidak tersedia'}), 401

    try:
        token = auth_header.split(" ")[1]
        decoded_token = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = decoded_token['user_id']
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token kadaluarsa'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Token tidak valid'}), 401

    data = request.get_json()
    full_name = data.get('full_name')
    address = data.get('address')
    city = data.get('city')
    zip_code = data.get('zip_code')
    phone = data.get('phone')
    email = data.get('email')
    items = data.get('items')
    total_amount = data.get('total_amount')

    if not all([full_name, address, city, zip_code, phone, email, items, total_amount]):
        return jsonify({'message': 'Semua detail pesanan harus diisi'}), 400
    
    if not items:
        return jsonify({'message': 'Keranjang kosong, tidak ada item untuk dipesan'}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({'message': 'Gagal terhubung ke database'}), 500

    try:
        cursor = conn.cursor()
        insert_order_query = """
        INSERT INTO orders (user_id, total_amount, full_name, address, city, zip_code, phone, email)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(insert_order_query, (user_id, total_amount, full_name, address, city, zip_code, phone, email))
        cursor.execute("SELECT SCOPE_IDENTITY() AS id")
        order_id = cursor.fetchone()[0]

        insert_order_item_query = """
        INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase)
        VALUES (?, ?, ?, ?)
        """
        for item in items:
            product_id = item['id']
            quantity = item['quantity']
            price_at_purchase = item['price']
            cursor.execute(insert_order_item_query, (order_id, product_id, quantity, price_at_purchase))
            
            update_stock_query = "UPDATE products SET stock = stock - ? WHERE id = ?"
            cursor.execute(update_stock_query, (quantity, product_id))

        clear_cart_query = "DELETE FROM carts WHERE user_id = ?"
        cursor.execute(clear_cart_query, (user_id,))

        conn.commit()
        return jsonify({'message': 'Pesanan berhasil ditempatkan!', 'order_id': order_id}), 201

    except Error as e:
        conn.rollback()
        print(f"Database Error during order placement: {e}")
        return jsonify({'message': f'Gagal menempatkan pesanan: {e}'}), 500
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
