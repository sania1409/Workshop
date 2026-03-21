from passlib.hash import scrypt

password = "piaadmin123"
hashed = "$scrypt$ln=16,r=8,p=1$/D/HWIsRotS6V4oR4vzf+w$Gf++hl/PqZkP/nfQNw/PrObD8X1bLGPsdAxt01qBtMk"

if scrypt.verify(password, hashed):
    print("Password is correct ✅")
else:
    print("Password is incorrect ❌")