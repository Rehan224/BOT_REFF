import imaplib
import ssl
import logging
from email.header import decode_header
from email import policy
from email.parser import BytesParser
import requests
import time
import re
from colorama import Fore, Style, init
from faker import Faker
import random
import json
import string
import names

# Inisialisasi colorama dan Faker
init(autoreset=True)
fake = Faker()

# Logging
logging.disable(logging.CRITICAL)

# Fungsi untuk menghubungkan dan login ke IMAP
def connect_imap(username, password, retries=3):
    attempt = 0
    while attempt < retries:
        try:
            mail = imaplib.IMAP4_SSL("imap-mail.outlook.com")
            mail.login(username, password)
            return mail
        except ssl.SSLError as e:
            logging.error(f"SSL error occurred: {e}")
        except imaplib.IMAP4.abort as e:
            logging.error(f"IMAP abort error: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
        attempt += 1
        time.sleep(5)  # Tunggu beberapa detik sebelum mencoba lagi
    return None

# Fungsi untuk mencari email dengan subjek tertentu
def search_email(mail, subject):
    try:
        mail.select("inbox")
        status, messages = mail.search(None, 'ALL')
        email_ids = messages[0].split()

        for email_id in reversed(email_ids):
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = BytesParser(policy=policy.default).parsebytes(response_part[1])
                    msg_subject = decode_header(msg["Subject"])[0][0]
                    if isinstance(msg_subject, bytes):
                        msg_subject = msg_subject.decode()
                    if subject in msg_subject:
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                if content_type == "text/plain":
                                    body = part.get_payload(decode=True).decode()
                                    return body
                        else:
                            body = msg.get_payload(decode=True).decode()
                            return body
    except imaplib.IMAP4.abort as e:
        logging.error(f"IMAP abort error: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
    return None

# Fungsi lainnya tetap sama
# Fungsi untuk mengekstrak OTP dari body email
def extract_otp(body):
    otp_match = re.search(r'Here is your Pixelverse OTP: (\d+)', body)
    if otp_match:
        return otp_match.group(1)
    return None

# Fungsi untuk mengirim permintaan OTP
def request_otp(email, delay=20):
    try:
        response = requests.post('https://api.pixelverse.xyz/api/otp/request', json={'email': email})
        if response.status_code == 200:
            return True
        elif response.status_code == 429:
            print("Tunggu beberapa detik")
            time.sleep(delay)
            return request_otp(email, delay)
        else:
            return False
    except Exception as e:
        print(f"Exception occurred while requesting OTP for {email}: {str(e)}")
        return False

# Fungsi untuk memverifikasi OTP
def verify_otp(email, otp):
    response = requests.post('https://api.pixelverse.xyz/api/auth/otp', json={'email': email, 'otpCode': otp})
    if response.status_code in [200, 201]:
        refresh_token_cookie = response.cookies.get('refresh-token')
        try:
            data = response.json()
        except ValueError:
            print(f"Respon JSON tidak valid untuk {email}. Status: {response.status_code}, Respon: {response.text}")
            return None

        data['refresh_token'] = refresh_token_cookie
        if 'tokens' in data and 'access' in data['tokens']:
            data['access_token'] = data['tokens']['access']
            return data
        else:
            print(f"Respon tidak mengandung tokens['access'] untuk {email}. Respon: {data}")
    else:
        print(f"Verifikasi OTP gagal. Status: {response.status_code}, Respon: {response.text}")
    return None

# Fungsi untuk mengatur referral
def set_referral(referral_code, access_token):
    headers = {
        'Authorization': access_token,  # tanpa 'Bearer'
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Origin': 'https://dashboard.pixelverse.xyz',
        'Referer': 'https://dashboard.pixelverse.xyz/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, seperti Gecko) Chrome/126.0.0.0 Safari/537.36'
    }
    referral_url = f'https://api.pixelverse.xyz/api/referrals/set-referer/{referral_code}'
    response = requests.put(referral_url, headers=headers)
    try:
        response_json = response.json()
    except ValueError:
        response_json = None
    return response.status_code, response_json

# Fungsi untuk memperbarui username dan biography
def update_username_and_bio(access_token):
    url = "https://api.pixelverse.xyz/api/users/@me"
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'en-US,en;q=0.9',
        'Authorization': access_token,
        'Cache-Control': 'no-cache',
        'Content-Type': 'application/json',
        'Origin': 'https://dashboard.pixelverse.xyz',
        'Referer': 'https://dashboard.pixelverse.xyz/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, seperti Gecko) Chrome/126.0.0.0 Safari/537.36'
    }
    username = names.get_first_name()  # Gunakan names module untuk username
    biography = fake.sentence()
    payload = {
        "updateProfileOptions": {
            "username": username,
            "biography": biography
        }
    }
    response = requests.patch(url, headers=headers, json=payload)
    if response.status_code == 200:
        print(Fore.GREEN + Style.BRIGHT + f"Username berhasil diperbarui menjadi: {username}")
        print(Fore.GREEN + Style.BRIGHT + f"Bio berhasil diperbarui menjadi: {biography}")
    else:
        print(Fore.RED + Style.BRIGHT + f"Gagal memperbarui username. Status: {response.status_code}, Respon: {response.text}")
    return response.status_code == 200


# Fungsi untuk membeli pet
def buy_pet(access_token, pet_id):
    url = f"https://api.pixelverse.xyz/api/pets/{pet_id}/buy"
    headers = {
        'Authorization': access_token,
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Origin': 'https://dashboard.pixelverse.xyz',
        'Referer': 'https://dashboard.pixelverse.xyz/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, seperti Gecko) Chrome/126.0.0.0 Safari/537.36'
    }
    response = requests.post(url, headers=headers)
    if response.status_code in [200, 201]:
        print(Fore.GREEN + Style.BRIGHT + "Pet berhasil dibeli!")
        return response.status_code, response.json()
    else:
        print(Fore.RED + Style.BRIGHT + f"Gagal membeli pet. Status: {response.status_code}, Respon: {response.text}")
    return None, None

# Fungsi untuk memilih pet
def select_pet(access_token, pet_data):
    pet_id = pet_data['id']
    url = f"https://api.pixelverse.xyz/api/pets/user-pets/{pet_id}/select"
    headers = {
        'Authorization': access_token,
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Origin': 'https://dashboard.pixelverse.xyz',
        'Referer': 'https://dashboard.pixelverse.xyz/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, seperti Gecko) Chrome/126.0.0.0 Safari/537.36'
    }
    response = requests.post(url, headers=headers)
    if response.status_code == 200:
        print(Fore.GREEN + Style.BRIGHT + "Pet berhasil dipilih!")
        return True
    elif response.status_code == 201:
        print(Fore.GREEN + Style.BRIGHT + "Pet sudah dipilih sebelumnya.")
        return True
    elif response.status_code == 400 and response.json().get('message') == "You have already selected this pet":
        print(Fore.GREEN + Style.BRIGHT + "Pet berhasil dipilih!")
        return True
    else:
        print(Fore.RED + Style.BRIGHT + f"Gagal memilih pet. Status: {response.status_code}, Respon: {response.text}")
    return False

# Fungsi untuk mengklaim daily reward
def claim_daily_reward(access_token):
    url = "https://api.pixelverse.xyz/api/daily-reward/complete"
    headers = {
        'Authorization': access_token,
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Origin': 'https://dashboard.pixelverse.xyz',
        'Referer': 'https://dashboard.pixelverse.xyz/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, seperti Gecko) Chrome/126.0.0.0 Safari/537.36'
    }
    try:
        response = requests.post(url, headers=headers)
        if response.status_code in [200, 201]:
            print(Fore.GREEN + Style.BRIGHT + "Daily reward berhasil diklaim!")
            return True
        else:
            print(Fore.RED + Style.BRIGHT + f"Gagal mengklaim daily reward. Status: {response.status_code}, Respon: {response.text}")
    except Exception as e:
        print(Fore.RED + Style.BRIGHT + f"Gagal mengklaim daily reward: {str(e)}")
    return False

# Fungsi untuk menghasilkan email acak on-the-fly
def generate_random_email(base_email):
    email_parts = base_email.split('@')
    random_string = ''.join(random.choices(string.ascii_lowercase, k=random.randint(3, 8)))
    generated_email = f"{email_parts[0]}+{random_string}@{email_parts[1]}"
    return generated_email

# Fungsi untuk mencoba kembali koneksi ke IMAP
def reconnect_imap(mail, username, password):
    try:
        mail.logout()
    except Exception as e:
        logging.error(f"Error during logout: {e}")
    time.sleep(15)  # Tunggu 15 detik sebelum mencoba login kembali
    return connect_imap(username, password)

# Fungsi untuk mencoba kembali koneksi ke IMAP dengan logout dan login ulang
def logout_and_reconnect(mail, username, password):
    try:
        mail.logout()
    except Exception as e:
        logging.error(f"Error during logout: {e}")
    time.sleep(15)  # Tunggu beberapa detik sebelum mencoba login kembali
    return connect_imap(username, password)

# Load konfigurasi dari config.json
try:
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    config = {}

# Fungsi utama untuk mengatur jumlah referral yang diinginkan
def main():
    global config

    # Input konfigurasi jika belum ada
    if not config:
        config['base_email'] = input("Masukkan Email Hotmail/Outlook: ")
        config['password'] = input("Masukkan Password: ")
        config['referral_code'] = input("Masukkan Referral Code: ")
        config['desired_referrals'] = int(input("Masukkan Jumlah Referral yang Diinginkan: "))
        with open('config.json', 'w') as config_file:
            json.dump(config, config_file, indent=4)
        print(Fore.GREEN + Style.BRIGHT + "Konfigurasi disimpan ke config.json")

    base_email = config['base_email']
    imap_password = config['password']
    referral_code = config['referral_code']
    desired_referrals = config['desired_referrals']

    # Hubungkan ke IMAP
    mail = connect_imap(base_email, imap_password)
    if not mail:
        print(Fore.RED + Style.BRIGHT + "Gagal terhubung ke server IMAP.")
        return

    # Daftar untuk melacak email yang berhasil
    successful_emails = []

    # Proses setiap email hingga jumlah referral tercapai
    for index in range(1, desired_referrals + 1):
        if len(successful_emails) >= desired_referrals:
            break

        email = generate_random_email(base_email)
        print(Fore.CYAN + Style.BRIGHT + f"Proses email Ke-{index}: {email}")

        try:
            if request_otp(email):
                print(Fore.YELLOW + Style.BRIGHT + f"OTP diminta untuk {email}. Tunggu beberapa detik...")
                time.sleep(20)  # Tunggu beberapa detik agar email OTP dapat diterima

                otp_subject = "Pixelverse Authorization"  # Sesuaikan dengan subjek email OTP yang diterima
                otp_body = search_email(mail, otp_subject)

                if otp_body:
                    otp_code = extract_otp(otp_body)
                    if otp_code:
                        print(Fore.GREEN + Style.BRIGHT + f"OTP diterima: {otp_code}")
                        auth_data = verify_otp(email, otp_code)

                        if auth_data and 'access_token' in auth_data:
                            access_token = auth_data['access_token']
                            print(Fore.GREEN + Style.BRIGHT + f"Token akses diterima")
                            random_referral_code = random.choice(referral_code)
                            status_code, response_json = set_referral(random_referral_code, access_token)
                            if status_code in [200, 201]:
                                print(Fore.GREEN + Style.BRIGHT + f"Berhasil menggunakan referral code: {random_referral_code}")
                                if update_username_and_bio(access_token):
                                    pet_id = "27977f52-997c-45ce-9564-a2f585135ff5"
                                    pet_status, pet_data = buy_pet(access_token, pet_id)
                                    if pet_status in [200, 201]:
                                        if select_pet(access_token, pet_data):
                                            if claim_daily_reward(access_token):
                                                print(Fore.BLUE + Style.BRIGHT + f"Referral Ke-{index} Berhasil")
                                                successful_emails.append(email)
                            else:
                                print(Fore.RED + Style.BRIGHT + f"Referral set gagal untuk {email}. Status: {status_code}, Respon: {response_json}")
                                print(Fore.RED + Style.BRIGHT + f"Referral Ke-{index} Gagal")
                        else:
                            print(Fore.RED + Style.BRIGHT + f"Verifikasi OTP gagal untuk {email}. Tidak ada access_token dalam respon.")
                            print(Fore.RED + Style.BRIGHT + f"Referral Ke-{index} Gagal")
                    else:
                        print(Fore.RED + Style.BRIGHT + f"Tidak dapat mengekstrak OTP untuk {email}.")
                        print(Fore.RED + Style.BRIGHT + f"Referral Ke-{index} Gagal")
                else:
                    print(Fore.RED + Style.BRIGHT + f"Tidak dapat menemukan email OTP untuk {email}. Logout dan mencoba lagi.")
                    mail = logout_and_reconnect(mail, base_email, imap_password)
                    if not mail:
                        print(Fore.RED + Style.BRIGHT + "Gagal terhubung kembali ke server IMAP. Menghentikan skrip.")
                        break
                    print(Fore.RED + Style.BRIGHT + f"Referral Ke-{index} Gagal")
            else:
                print(Fore.RED + Style.BRIGHT + f"Permintaan OTP gagal untuk {email}.")
                print(Fore.RED + Style.BRIGHT + f"Referral Ke-{index} Gagal")
        except imaplib.IMAP4.abort as e:
            logging.error(f"IMAP abort error: {e}")
            print(Fore.RED + Style.BRIGHT + f"Terjadi kesalahan IMAP untuk email {email}. Mencoba untuk reconnect...")
            mail = reconnect_imap(mail, base_email, imap_password)
            if not mail:
                print(Fore.RED + Style.BRIGHT + "Gagal terhubung kembali ke server IMAP. Menghentikan skrip.")
                break
        except Exception as e:
            print(Fore.RED + Style.BRIGHT + f"Terjadi kesalahan saat memproses email {email}: {e}")
            logging.error(f"Error processing email {email}: {e}")

    # Keluar dari server IMAP
    if mail:
        mail.logout()
    print(Fore.GREEN + Style.BRIGHT + f"Proses referral selesai. {len(successful_emails)} referral berhasil.")

# Jalankan fungsi utama
if __name__ == "__main__":
    main()
