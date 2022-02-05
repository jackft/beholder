import subprocess


def generate_random_key(key_path) -> int:
    with key_path.open("w") as f:
        return subprocess.call(["openssl", "rand", "-base64", "32"], stdout=f)


def encrypt_file(input_file_path, key_path, output_file_path) -> int:
    return subprocess.call([
        "openssl", "enc", "-aes-256-cbc", "-salt",
        "-in", str(input_file_path),
        "-out", str(output_file_path),
        "--pass", f"file:{key_path}"
    ])

def decrypt_file(input_file_path, key_path, output_file_path) -> int:
    return subprocess.call([
        "openssl", "enc", "-aes-256-cbc", "-d",
        "-in", str(input_file_path),
        "-out", str(output_file_path),
        "--pass", f"file:{key_path}"
    ])
