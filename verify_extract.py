import os
import hashlib
import zipfile

def verify_and_extract(base_name):
    zip_filename = f"{base_name}.zip"
    hash_filename = f"{base_name}_sha256sums.txt"

    # Kiểm tra file có tồn tại không
    if not os.path.exists(zip_filename) or not os.path.exists(hash_filename):
        print(f"Lỗi: Không tìm thấy file '{zip_filename}' hoặc '{hash_filename}'")
        return

    print(f"Đang kiểm tra file: {zip_filename}")

    with open(hash_filename, 'r') as f:
        stored_hash = f.read().strip()

    sha256_hasher = hashlib.sha256()
    with open(zip_filename, 'rb') as f:
        # Đọc từng khối 4KB để tiết kiệm RAM
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hasher.update(byte_block)
    
    calculated_hash = sha256_hasher.hexdigest()

    if stored_hash == calculated_hash:
        print(f"HASH KHỚP! File an toàn.")
        print(f"Hash: {calculated_hash}")
        
        extract_folder = f"{base_name}_extracted"
        print(f"Đang giải nén vào thư mục: '{extract_folder}'")
        
        try:
            with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
            print("Hoàn tất giải nén")
        except Exception as e:
            print(f"Lỗi khi giải nén: {e}")
            
    else:
        print(f"CẢNH BÁO: MÃ HASH KHÔNG KHỚP!")
        print(f"    Hash gốc (trong txt): {stored_hash}")
        print(f"    Hash hiện tại (zip):  {calculated_hash}")


if __name__ == "__main__":
    target_folder = "Đồng Bằng sông Cửu Long – Nét sinh hoạt xưa và văn minh miệt vườn.pdf"
    verify_and_extract(target_folder)