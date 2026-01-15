import psycopg2
from passlib.context import CryptContext

# 1. Setup the password hasher
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 2. Generate a valid hash for "123456"
#    This handles all the complex characters safely
new_password_hash = pwd_context.hash("123456")
print(f"Generated Hash: {new_password_hash}")

try:
    # 3. Connect to Database
    conn = psycopg2.connect(
        dbname="ciegall",
        user="roadvision",
        password="FlyMeToTheMoon",
        host="localhost",
        port="5432"
    )
    cursor = conn.cursor()

    # 4. Update ALL users to have password "123456"
    #    (We use a parameterized query to prevent escaping issues)
    query = "UPDATE users SET hashed_password = %s;"
    cursor.execute(query, (new_password_hash,))
    
    conn.commit()
    print("✅ Successfully reset ALL user passwords to '123456'")

except Exception as e:
    print(f"❌ Error: {e}")

finally:
    if 'conn' in locals() and conn:
        conn.close()