Đầu tiên audio và text vào cùng 1 thư mục để có thể dùng MFA
Sau đó chạy docker với câu lệnh:
docker run -it --rm -v "(Đường dẫn đến thư mục của folder chứa audio và text):/data" mmcauliffe/montreal-forced-aligner:latest mfa align /data/(tên thư mục chứa audio và text) /data/vietnamese_hanoi_mfa.dict /data/vietnamese_mfa.zip /data/output --beam 100 --retry_beam 400
Sau khi algin xong thì sẽ có 1 vài ký từ k đọc được vì từ điển có giới hạn, nó sẽ được lưu dưới dạng <unk>.=>> Thực hiện đọc file lại bằng cách chạy Fix_unk.py
Cuối cùng chạy To_smil_file.py để sinh ra file .smil và .xml
