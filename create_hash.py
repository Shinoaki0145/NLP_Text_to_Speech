import os
import shutil
import hashlib


def create_zip_and_hash(folder_name):
    if not os.path.exists(folder_name):
        print(f"Lỗi: Không tìm thấy thư mục '{folder_name}'")
        return

    print(f"Đang nén thư mục '{folder_name}'")
    
    # Tạo file zip
    zip_filename = shutil.make_archive(base_name=folder_name, format='zip', base_dir=folder_name)
    print(f"Đã tạo: {zip_filename}")

    print("Đang tính mã SHA-256")
    # Tính hash của file zip vừa tạo
    sha256_hash = hashlib.sha256()
    with open(zip_filename, "rb") as f:
        # Đọc file theo từng khối nhỏ để tối ưu RAM
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    
    checksum = sha256_hash.hexdigest()
    
    hash_filename = f"{folder_name}_sha256sums.txt"
    
    with open(hash_filename, 'w') as f:
        f.write(checksum)
        
    print(f"Đã tạo file hash: {hash_filename}")
    print(f"Mã Hash là: {checksum}")


if __name__ == "__main__":
    target_folder = os.path.join("book", "Đồng Bằng sông Cửu Long Nét sinh hoạt xưa và văn minh miệt vườn.pdf") 
    create_zip_and_hash(target_folder)