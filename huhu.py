import re
import os
import unicodedata
import logging
import pdfplumber
from collections import Counter

# Tắt log rác của pdfminer
logging.getLogger("pdfminer").setLevel(logging.ERROR)

class UltimatePDFCleaner:
    def __init__(self):
        self.garbage_phrases = [
            "Ồ Ằ", "Ổ Ầ", "Ồ Ầ", "Ể ", "", "", ""
        ]
        # Danh sách từ khóa để nhận diện dòng Metadata (không xử lý footnote ở đây)
        self.meta_keywords = [
            "Copyright", "Cataloging", "biên khảo", "NXB", "NHÀ XUẤT BẢN", 
            "Publishing House", "BIỂU GHI", "THƯ VIỆN", "All rights reserved"
        ]
        self.meta_connectors = ["-", "--", "–", "và", ":", ","]
    
    def clean_string(self, text):
        if not text: return ""
        text = unicodedata.normalize('NFKC', text)
        
        # Xóa rác đầu dòng
        text = re.sub(r'^[\s•●_]+', '', text)
        
        for phrase in self.garbage_phrases:
            text = text.replace(phrase, "")

        # Backup: Đảm bảo footnote [1] dính vào từ trước nếu bị tách
        text = re.sub(r'\s+(\[\d+\])', r'\1', text)

        # Đưa dấu câu lại sát từ trước
        text = re.sub(r'\s+([,.:;!?])', r'\1', text)
        
        # Xử lý ngoặc kép thẳng
        text = re.sub(r'"\s+', '"', text)
        text = re.sub(r'\s+"', '"', text)
        text = re.sub(r'(?<=[^\s(])"', ' "', text)
        text = re.sub(r'"(?=\w)', '" ', text)

        # Xử lý ngoặc kép cong
        text = re.sub(r'“\s+', '“', text)
        text = re.sub(r'\s+”', '”', text)
        text = re.sub(r'(?<=[^\s(])“', ' “', text)
        text = re.sub(r'”(?=\w)', '” ', text)
        
        # Tách Tựa đề trong ngoặc đơn sang dòng riêng (nếu ở đầu dòng)
        text = re.sub(r'^\(([^)]+)\)\s*', r'(\1)\n', text)
        
        return text.strip()
    
    def split_sentences(self, text):
        if not text: return []
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace('|||NEWLINE|||', '\n')
        
        # Bảo vệ các từ viết tắt (T.P., Tp., v.v.) không bị ngắt câu nhầm
        def protect_match(match):
            return match.group().replace('.', '<PR_DOT>')
        
        text = re.sub(r'(?<!\w)[A-Z][a-zA-Z]{0,2}\.(?=\s)', protect_match, text)
        
        viet_upper = "ÁÀẢÃẠÂẤẦẨẪẬĂẮẰẲẴẶÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ" 
        pattern = r'(?<=[.?!])\s+(?=[A-Z%s"\'\«\(\“\‘])' % viet_upper

        sentences = re.split(pattern, text)
        
        final_sentences = []
        for s in sentences:
            if s.strip():
                restored = s.replace('<PR_DOT>', '.')
                final_sentences.append(restored.strip())
        return final_sentences

    def get_lines_with_meta(self, page):
        words = page.extract_words(extra_attrs=['size'])
        if not words: return []

        # 1. Tính Body Size chuẩn của trang
        all_sizes = [w['size'] for w in words]
        if not all_sizes: return []
        page_body_size = Counter(all_sizes).most_common(1)[0][0]

        # 2. GOM DÒNG VẬT LÝ (Clustering theo trục Y)
        words.sort(key=lambda w: w['top'])
        
        lines_cluster = []
        current_cluster = []
        
        if words:
            current_cluster = [words[0]]
            for w in words[1:]:
                avg_top = sum([x['top'] for x in current_cluster]) / len(current_cluster)
                # Cho phép lệch 6 points (để gom cả số mũ bị lệch lên trên)
                if abs(w['top'] - avg_top) < 6: 
                    current_cluster.append(w)
                else:
                    lines_cluster.append(current_cluster)
                    current_cluster = [w]
            lines_cluster.append(current_cluster)

        # 3. XỬ LÝ TỪNG DÒNG
        processed_lines = []
        
        for cluster in lines_cluster:
            # Sắp xếp từ trái sang phải (QUAN TRỌNG để số mũ ra đúng vị trí)
            cluster.sort(key=lambda w: w['x0'])
            
            # --- CHECK CONTEXT: Dòng này có phải Metadata không? ---
            raw_line_text = " ".join([w['text'] for w in cluster])
            is_meta_line = any(kw in raw_line_text for kw in self.meta_keywords)
            
            merged_words_in_line = []
            
            for w in cluster:
                text_clean = w['text'].strip()
                
                # Điều kiện nhận diện Footnote
                is_digit = text_clean.isdigit() or (text_clean.startswith('[') and text_clean.endswith(']'))
                
                # Nhỏ hơn body size HOẶC nằm cao hơn hẳn so với dòng
                is_small = w['size'] < (page_body_size * 0.98)
                line_avg_top = sum([x['top'] for x in cluster]) / len(cluster)
                is_superscript = (line_avg_top - w['top']) > 1
                
                # Chỉ xử lý số có ít hơn 4 chữ số (để tránh năm 2009, 1995)
                is_short_number = len(re.sub(r'[\[\]]', '', text_clean)) < 4

                # QUYẾT ĐỊNH: Đóng khung và gộp
                if is_digit and (is_small or is_superscript) and not is_meta_line and is_short_number:
                    
                    raw_num = re.sub(r'[\[\]]', '', text_clean) 
                    formatted_text = f"[{raw_num}]"
                    
                    merged = False
                    if merged_words_in_line:
                        prev_w = merged_words_in_line[-1]
                        # Nếu khoảng cách ngang < 6 -> Gộp vào từ trước
                        dist_x = w['x0'] - prev_w['x1']
                        
                        if dist_x < 6:
                            prev_w['text'] += formatted_text
                            prev_w['x1'] = w['x1'] # Update boundary
                            merged = True
                    
                    if not merged:
                        w['text'] = formatted_text
                        merged_words_in_line.append(w)
                else:
                    merged_words_in_line.append(w)

            text = " ".join([w['text'] for w in merged_words_in_line])
            max_size = max([w['size'] for w in cluster]) if cluster else 0
            
            clean_text = self.clean_string(text)
            if clean_text:
                processed_lines.append({'text': clean_text, 'size': round(max_size, 1)})
                
        return processed_lines

    def analyze_font_structure(self, all_lines):
        if not all_lines: return 12
        sizes = [line['size'] for line in all_lines]
        if not sizes: return 12
        size_counts = Counter(sizes)
        return size_counts.most_common(1)[0][0]

    def final_text_repair(self, text_list):
        # Sửa lỗi ngắt dòng tên địa danh phổ biến
        full_text = "\n".join(text_list)
        full_text = re.sub(r'(T\.P\.)\s*[\n\r]+\s*(Hồ)', r'\1 \2', full_text)
        full_text = re.sub(r'(Hồ\s+Chí)\s*[\n\r]+\s*(Minh)', r'\1 \2', full_text)
        full_text = re.sub(r'(Hồ)\s*[\n\r]+\s*(Chí\s+Minh)', r'\1 \2', full_text)
        return full_text.split('\n')

    def process_hybrid_structure(self, all_lines, body_size):
        final_output = []
        text_buffer = []
        
        HEADER_THRESHOLD = body_size + 1.5 
        prev_type = None
        last_header_size = 0

        for line in all_lines:
            text = line['text']
            size = line['size']
            
            # Cleaner dấu *
            text = re.sub(r'\s*\*\s+\*\s+\*\s*', ' ', text)
            text = re.sub(r'\*{3,}', ' ', text)
            text = re.sub(r'(?:\s*\*\s*){3,}', ' ', text)
            text = text.strip()
            
            if not text or text.replace('*', '').replace(' ', '') == '':
                if text_buffer:
                    final_output.extend(self.split_sentences(" ".join(text_buffer)))
                    text_buffer = []
                prev_type = 'SEPARATOR'
                continue
            
            # --- DETECTOR ---
            is_bullet_char = re.match(r'^[-+]\s+', text) or re.match(r'^\d+\.\s+', text)
            is_meta_keyword = any(k in text for k in self.meta_keywords)
            is_library_code = re.match(r'^\d{3}\.\d+', text) or re.search(r'dc\s*22', text)
            
            # Check mô tả vật lý (424 tr.; 20cm) để tách dòng
            is_physical_desc = re.match(r'^\d+\s*(tr\.|tr;|trang|p\.|cm)', text, re.IGNORECASE)

            current_type = 'TEXT'
            is_big_header = (size >= HEADER_THRESHOLD and text.isupper())
            is_sub_header = (text.isupper() and size >= body_size and len(text.split()) < 20)

            if is_bullet_char or is_meta_keyword or is_library_code or is_physical_desc:
                current_type = 'META'
            elif is_big_header or is_sub_header: 
                current_type = 'HEADER'

            # --- LOGIC GỘP/TÁCH DÒNG ---
            should_merge_meta = False
            if prev_type == 'META' and final_output:
                last_line = final_output[-1]
                # Chỉ nối nếu dòng trước có dấu hiệu liệt kê
                if any(last_line.endswith(c) for c in self.meta_connectors) or text[0].islower(): 
                    should_merge_meta = True

            if should_merge_meta:
                if text_buffer:
                    final_output.extend(self.split_sentences(" ".join(text_buffer)))
                    text_buffer = []
                prev_text = final_output.pop()
                final_output.append(prev_text + " " + text)
                prev_type = 'META'
                continue 

            if current_type == 'META':
                # Gặp META mới -> Flush buffer cũ
                if text_buffer:
                    final_output.extend(self.split_sentences(" ".join(text_buffer)))
                    text_buffer = []
                final_output.append(text)
                prev_type = 'META'

            elif current_type == 'HEADER':
                should_merge_header = False
                if prev_type == 'HEADER' and abs(size - last_header_size) < 0.5:
                    should_merge_header = True

                if should_merge_header:
                    prev_text = final_output.pop()
                    final_output.append(prev_text + " " + text)
                else:
                    if text_buffer:
                        final_output.extend(self.split_sentences(" ".join(text_buffer)))
                        text_buffer = []
                    final_output.append(text)
                
                prev_type = 'HEADER'
                last_header_size = size     
            else: # TEXT
                should_merge = False
                if text_buffer:
                    prev_line = text_buffer[-1].strip()
                    
                    # Logic nối đoạn văn
                    if text[0].islower() or text[0].isdigit() or text.startswith('['):
                        should_merge = True
                    elif re.search(r'(?:^|[\s.])([A-Z][a-zA-Z]{0,2}\.)$', prev_line):
                        should_merge = True
                    elif prev_line.endswith(',') or prev_line.endswith('-') or prev_line.endswith('–'):
                        should_merge = True

                if should_merge:
                    if text_buffer[-1].endswith('-'):
                         text_buffer[-1] = text_buffer[-1][:-1] + text
                    else:
                         text_buffer[-1] = text_buffer[-1] + " " + text
                else:
                    text_buffer.append(text)
                prev_type = 'TEXT'
            
        if text_buffer:
            final_output.extend(self.split_sentences(" ".join(text_buffer)))

        return self.final_text_repair(final_output)

    def extract_and_clean(self, pdf_path, output_txt_path):
        print(f"Đang xử lý file: {pdf_path}")
        all_lines_with_meta = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    print(f"Đang đọc: {i+1}/{len(pdf.pages)}", end='\r')
                    all_lines_with_meta.extend(self.get_lines_with_meta(page))

            print("\nĐang làm sạch & Tái cấu trúc")
            body_size = self.analyze_font_structure(all_lines_with_meta)
            final_lines = self.process_hybrid_structure(all_lines_with_meta, body_size)
            
            with open(output_txt_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(final_lines))
            print(f"Hoàn tất! File lưu tại: {output_txt_path}")
        except Exception as e:
            print(f"\nLỗi: {e}")

# ĐƯỜNG DẪN FILE CỦA BẠN
input_file = os.path.join("book", "Đồng Bằng sông Cửu Long Nét sinh hoạt xưa và văn minh miệt vườn.pdf") 
output_file = "format_text.txt"

if __name__ == "__main__":
    cleaner = UltimatePDFCleaner()
    cleaner.extract_and_clean(input_file, output_file)