import base64
import hmac
import hashlib

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5 as PKCS1_cipher


def get_key(key_file):
    with open(key_file) as f:
        data = f.read()
        key = RSA.importKey(data)
    return key


def decrypt_data(encrypt_data):
    private_key = get_key('static/rsa_private_key.pem')
    cipher = PKCS1_cipher.new(private_key)
    back_text = cipher.decrypt(base64.b64decode(encrypt_data), 0).decode('utf-8')
    pwd = decode_pwd(back_text)
    return pwd


def decode_pwd(encode_pwd):
    try:
        uni_pwd = encode_pwd.split('WebSpider')[1]
    except IndexError:
        raise ValueError("密码解密失败，请检查加密是否正确")
    pwd = ""
    for char in uni_pwd:
        unicode_value = ord(char)
        source_value = unicode_value - 1
        source_char = chr(source_value)
        pwd += source_char
    return pwd


def generate_signature(secret: str, method: str, path: str, timestamp: str, body: str) -> str:
    # 构造签名字符串，顺序必须严格一致
    message = f"{method}|{path}|{timestamp}|{body}"
    return hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


async def encode_password(password: str, salt: str):
    msg = f"{password}{salt}"
    secret = hashlib.sha512(msg.encode()).hexdigest()
    return secret