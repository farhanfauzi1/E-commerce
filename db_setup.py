import pyodbc
from pyodbc import Error
import hashlib

# Fungsi koneksi diubah untuk Windows Authentication
def create_db_connection(server, database, driver="{ODBC Driver 17 for SQL Server}"):
    """
    Membuat koneksi ke database SQL Server menggunakan Windows Authentication.
    """
    connection = None
    try:
        conn_str = (
            f"DRIVER={driver};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"Trusted_Connection=yes;" # Menggunakan Windows Authentication
        )
        connection = pyodbc.connect(conn_str, autocommit=True) # autocommit=True untuk DDL
        print("Koneksi database SQL Server berhasil menggunakan Windows Authentication!")
    except Error as e:
        print(f"Error: '{e}'")
    return connection

def execute_query(connection, query, params=None):
    """
    Menjalankan query SQL.
    """
    cursor = connection.cursor()
    try:
        cursor.execute(query, params or ())
        print("Query berhasil dieksekusi")
        return True
    except Error as e:
        print(f"Error: '{e}'")
        return False
    finally:
        cursor.close()

def fetch_query(connection, query, params=None):
    """
    Mengambil data dari query SQL.
    """
    cursor = connection.cursor()
    try:
        cursor.execute(query, params or ())
        columns = [column[0] for column in cursor.description]
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        return results
    except Error as e:
        print(f"Error: '{e}'")
        return None
    finally:
        cursor.close()

def hash_password(password):
    """
    Menghash password menggunakan SHA256.
    """
    return hashlib.sha256(password.encode()).hexdigest()

def setup_database(connection, db_name):
    """
    Mengatur tabel yang diperlukan untuk aplikasi e-commerce di SQL Server.
    """
    create_users_table = """
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='users' and xtype='U')
    CREATE TABLE users (
        id INT IDENTITY(1,1) PRIMARY KEY,
        username NVARCHAR(255) NOT NULL UNIQUE,
        password NVARCHAR(255) NOT NULL,
        email NVARCHAR(255) UNIQUE,
        created_at DATETIME DEFAULT GETDATE()
    );
    """
    execute_query(connection, create_users_table)

    create_products_table = """
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='products' and xtype='U')
    CREATE TABLE products (
        id NVARCHAR(255) PRIMARY KEY,
        name NVARCHAR(255) NOT NULL,
        description NVARCHAR(MAX),
        price DECIMAL(10, 2) NOT NULL,
        original_price DECIMAL(10, 2),
        discount INT DEFAULT 0,
        image_url NVARCHAR(255),
        stock INT DEFAULT 0
    );
    """
    execute_query(connection, create_products_table)

    create_carts_table = """
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='carts' and xtype='U')
    CREATE TABLE carts (
        id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT,
        product_id NVARCHAR(255),
        quantity INT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    );
    """
    execute_query(connection, create_carts_table)

    create_orders_table = """
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='orders' and xtype='U')
    CREATE TABLE orders (
        id INT IDENTITY(1,1) PRIMARY KEY,
        user_id INT,
        order_date DATETIME DEFAULT GETDATE(),
        total_amount DECIMAL(10, 2) NOT NULL,
        full_name NVARCHAR(255),
        address NVARCHAR(MAX),
        city NVARCHAR(255),
        zip_code NVARCHAR(10),
        phone NVARCHAR(20),
        email NVARCHAR(255),
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """
    execute_query(connection, create_orders_table)

    create_order_items_table = """
    IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='order_items' and xtype='U')
    CREATE TABLE order_items (
        id INT IDENTITY(1,1) PRIMARY KEY,
        order_id INT,
        product_id NVARCHAR(255),
        quantity INT NOT NULL,
        price_at_purchase DECIMAL(10, 2) NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id),
        FOREIGN KEY (product_id) REFERENCES products(id)
    );
    """
    execute_query(connection, create_order_items_table)

    products = fetch_query(connection, "SELECT TOP 1 * FROM products")
    if not products:
        print("Menambahkan produk contoh...")
        sample_products = [
            ('product-1', 'Bell Pepper', 'Lada segar pilihan.', 100000.00, 120000.00, 30, 'images/product-1.jpg', 50),
            ('product-2', 'Strawberry', 'Stroberi manis dan segar.', 60000.00, None, 0, 'images/product-2.jpg', 100),
            ('product-3', 'Green Beans', 'Buncis hijau organik.', 40000.00, None, 0, 'images/product-3.jpg', 75),
            ('product-4', 'Purple Cabbage', 'Kol ungu segar.', 50000.00, None, 0, 'images/product-4.jpg', 60),
            ('product-5', 'Tomatoe', 'Tomat merah segar.', 40000.00, 80000.00, 30, 'images/product-5.jpg', 90),
            ('product-6', 'Brocolli', 'Brokoli hijau segar.', 20000.00, None, 0, 'images/product-6.jpg', 40),
            ('product-7', 'Carrots', 'Wortel renyah.', 15000.00, None, 0, 'images/product-7.jpg', 120),
            ('product-8', 'Fruit Juice', 'Jus buah segar.', 70000.00, None, 0, 'images/product-8.jpg', 80),
            ('product-9', 'Onion', 'Bawang bombay.', 100000.00, 120000.00, 30, 'images/product-9.jpg', 70),
            ('product-10', 'Apple', 'Apel merah segar.', 80000.00, None, 0, 'images/product-10.jpg', 110),
            ('product-11', 'Garlic', 'Bawang putih.', 70000.00, None, 0, 'images/product-11.jpg', 95),
            ('product-12', 'Chilli', 'Cabai pedas.', 50000.00, None, 0, 'images/product-12.jpg', 65)
        ]
        insert_product_query = """
        INSERT INTO products (id, name, description, price, original_price, discount, image_url, stock)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        for product in sample_products:
            execute_query(connection, insert_product_query, product)
        print("Produk contoh berhasil ditambahkan.")

if __name__ == "__main__":
    # Ganti dengan detail koneksi database SQL Server Anda
    # SERVER: Biasanya 'localhost' atau '.\SQLEXPRESS' atau nama server/IP
    # DATABASE: Nama database yang akan dibuat/digunakan
    # DRIVER: Sesuaikan dengan driver ODBC yang terinstal di sistem Anda.
    #         Contoh: "{ODBC Driver 17 for SQL Server}" atau "{SQL Server}"
    
    DB_SERVER = "LAPTOP-DU6E16BV" # Ganti dengan nama server SQL Server Anda
    DB_NAME = "FarhanShopDB" # Nama database yang akan dibuat

    # Koneksi ke master database untuk membuat database baru jika belum ada
    # Tidak perlu username/password karena menggunakan Trusted_Connection
    master_conn = create_db_connection(DB_SERVER, "master") # Perhatikan tidak ada username/password
    if master_conn:
        create_database_query = f"IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'{DB_NAME}') CREATE DATABASE {DB_NAME};"
        execute_query(master_conn, create_database_query)
        master_conn.close()
        print(f"Database '{DB_NAME}' siap digunakan.")

    # Koneksi langsung ke database yang baru dibuat/sudah ada untuk setup tabel
    connection = create_db_connection(DB_SERVER, DB_NAME) # Perhatikan tidak ada username/password
    if connection:
        setup_database(connection, DB_NAME)
        connection.close()
    else:
        print("Gagal terhubung ke database untuk setup tabel.")

