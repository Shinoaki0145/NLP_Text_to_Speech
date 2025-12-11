# NLP Text to Speech - DAISY Book Generation

Dự án này cung cấp các công cụ để tạo sách nói kỹ thuật số chuẩn DAISY từ văn bản và âm thanh, sử dụng Montreal Forced Aligner (MFA) để căn chỉnh thời gian.

## Quy trình thực hiện

### Bước 1: Chuẩn bị dữ liệu
Đưa các file **audio** và **text** vào cùng một thư mục. Điều này là cần thiết để MFA có thể đối chiếu văn bản với âm thanh.

### Bước 2: Chạy Montreal Forced Aligner (MFA)
Sử dụng Docker để chạy MFA và thực hiện căn chỉnh (alignment).

Chạy câu lệnh sau trong terminal:

```bash
docker run -it --rm -v "(Đường dẫn đến thư mục của folder chứa audio và text):/data" mmcauliffe/montreal-forced-aligner:latest mfa align /data/(tên thư mục chứa audio và text) /data/vietnamese_hanoi_mfa.dict /data/vietnamese_mfa.zip /data/output --beam 100 --retry_beam 400
```

**Lưu ý:**
*   Thay thế `(Đường dẫn đến thư mục của folder chứa audio và text)` bằng đường dẫn thực tế trên máy của bạn.
*   Thay thế `(tên thư mục chứa audio và text)` bằng tên thư mục tương ứng bên trong container (thường là tên thư mục bạn đã mount).

### Bước 3: Xử lý từ không xác định (Unknown Words)
Sau khi align xong, một số từ có thể không đọc được do giới hạn của từ điển và sẽ được lưu dưới dạng `<unk>`.

Thực hiện đọc file lại và sửa lỗi bằng cách chạy script:

```bash
python Fix_unk.py
```

### Bước 4: Tạo file SMIL và XML
Cuối cùng, chạy script để sinh ra các file định dạng `.smil` và `.xml`:

```bash
python To_xml_smil_file.py
```

---

## Luồng hoạt động của sách DAISY (DAISY Book Flow)

Dưới đây là mô tả toàn bộ tiến trình chạy sách DAISY:

1.  **User mở chương trình**
2.  Chương trình đọc `main.opf`
3.  Load danh sách tài nguyên, metadata
4.  Load `main.ncx`
5.  **User chọn Chương 1**
6.  Player nhảy đến `01.smil#s1`
7.  Đọc đoạn `<par>`
    *   Highlight text (`01.xml`)
    *   Phát audio từ `01.mp3`
8.  Khi đến `clipEnd` → chuyển sang `<par>` tiếp theo
