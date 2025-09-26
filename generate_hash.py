from werkzeug.security import generate_password_hash

# --- IMPORTANT: TYPE YOUR DESIRED PASSWORD HERE ---
my_password = "shreebalaji2024"

hashed_password = generate_password_hash(my_password)

print("\n--- COPY THE HASH BELOW AND PASTE IT INTO VERCEL ---\n")
print(hashed_password)
print("\n-----------------------------------------------------\n")