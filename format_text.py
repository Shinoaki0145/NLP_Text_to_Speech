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
            "Ồ Ằ", "Ổ Ầ", "Ồ Ầ", "Ể "
        ]
        # self.garbage_phrases = [
        #     "Tủ sách", "Ebook miễn phí", "hoccachlamgiau", 
        #     "Created by", "Watermark", "sacngoc", "Ồ Ằ", "Ổ Ầ", "Ồ Ầ", "Ể "
        # ]
        self.meta_keywords = [
            "Copyright", "Cataloging", "biên khảo", "NXB", "NHÀ XUẤT BẢN", 
            "Publishing House", "BIỂU GHI", "THƯ VIỆN"
        ]
        # Các từ/ký tự báo hiệu Metadata chưa kết thúc (để nối dòng)
        self.meta_connectors = ["-", "--", "–", "và", ":", ","]
    
    
    def clean_string(self, text):
        if not text: return ""
        text = unicodedata.normalize('NFKC', text)
        
        # Xóa các dấu rác đầu và cuối dòng
        text = re.sub(r'^[\s•●_]+', '', text)
        
        # Xóa các cụm từ rác - Ví dụ như ở các title
        for phrase in self.garbage_phrases:
            text = text.replace(phrase, "")

        # Backup: Đảm bảo footnote [1] dính vào từ trước nếu bị tách
        text = re.sub(r'\s+(\[\d+\])', r'\1', text)

        # Đưa dấu câu lại sát từ trước
        text = re.sub(r'\s+([,.:;!?])', r'\1', text)
        
        # Xử lý ngoặc kép thẳng
        # Xóa space thừa bên trong: " ABC " -> "ABC"
        text = re.sub(r'"\s+', '"', text) # Xóa space sau dấu mở
        text = re.sub(r'\s+"', '"', text) # Xóa space trước dấu đóng
        # Thêm space bên ngoài: abc"def -> abc "def
        text = re.sub(r'(?<=[^\s(])"', ' "', text)
        text = re.sub(r'"(?=\w)', '" ', text)

        # Xử lý ngoặc kép cong (Smart Quotes “ ”)
        # Xóa space thừa bên trong: " ABC " -> "ABC"
        text = re.sub(r'“\s+', '“', text) # Xóa space sau dấu mở
        text = re.sub(r'\s+”', '”', text) # Xóa space trước dấu đóng
        # Thêm space bên ngoài:
        text = re.sub(r'(?<=[^\s(])“', ' “', text) # Xóa space sau dấu mở
        text = re.sub(r'”(?=\w)', '” ', text) # Xóa space trước dấu đóng
        
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
        
        text = re.sub(r'(?<!\w)[A-Z][a-zA-Z]{0,1}\.(?=\s)', protect_match, text)
        
        viet_upper = "ÁÀẢÃẠÂẤẦẨẪẬĂẮẰẲẴẶÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ" 
        pattern = r'(?<=[.?!])\s+(?=[A-Z%s"\'\«\(\“\‘])' % viet_upper

        sentences = re.split(pattern, text)
        
        final_sentences = []
        for s in sentences:
            if s.strip():
                # Trả lại dấu chấm ban đầu
                restored = s.replace('<PR_DOT>', '.')
                final_sentences.append(restored.strip())
        return final_sentences


    def get_lines_with_meta(self, page):
        words = page.extract_words(extra_attrs=['size'])
        if not words: return []

        # Tính Body Size chuẩn của trang
        all_sizes = [w['size'] for w in words]
        if not all_sizes: return []
        page_body_size = Counter(all_sizes).most_common(1)[0][0]

        # Gom dòng vật lý (Clustering theo trục Y)
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

        processed_lines = []
        
        for cluster in lines_cluster:
            # Sắp xếp từ trái sang phải
            cluster.sort(key=lambda w: w['x0'])
            
            # Check dòng này có phải Metadata không
            raw_line_text = " ".join([w['text'] for w in cluster])
            is_meta_line = any(kw in raw_line_text for kw in self.meta_keywords)
            
            merged_words_in_line = []
            
            for w in cluster:
                text_clean = w['text'].strip()
                
                # Điều kiện nhận diện Footnote
                is_digit = text_clean.isdigit() or (text_clean.startswith('[') and text_clean.endswith(']'))
                
                # Nhỏ hơn body size hoặc nằm cao hơn hẳn so với dòng
                is_small = w['size'] < (page_body_size * 0.98)
                line_avg_top = sum([x['top'] for x in cluster]) / len(cluster)
                is_superscript = (line_avg_top - w['top']) > 1
                
                # Chỉ xử lý số có ít hơn 4 chữ số (để tránh năm 2009, 1995)
                is_short_number = len(re.sub(r'[\[\]]', '', text_clean)) < 4

                # Đóng khung và gộp
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
        full_text = "\n".join(text_list)
        
        # Sửa lỗi ngắt dòng tên địa danh phổ biến (Tp., T.P.)
        full_text = re.sub(r'(T\.P\.)\s*[\n\r]+\s*(Hồ)', r'\1 \2', full_text)
        full_text = re.sub(r'(Hồ\s+Chí)\s*[\n\r]+\s*(Minh)', r'\1 \2', full_text)
        full_text = re.sub(r'(Hồ)\s*[\n\r]+\s*(Chí\s+Minh)', r'\1 \2', full_text)
        
        # Danh sách từ viết tắt địa chỉ
        address_patterns = [r'p\.', r'q\.', r'tp\.', r'tx\.', r'k\.', r'v\.', r'đ\.']
        
        viet_upper = "A-ZÁÀẢÃẠÂẤẦẨẪẬĂẮẰẲẴẶÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ" 
        
        for pat in address_patterns:
            regex = r'(?<!\w)(' + pat + r')\s*[\n\r]+\s*([' + viet_upper + r'])'
            full_text = re.sub(regex, r'\1 \2', full_text)

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
            
            # Xóa các pattern ***
            # Pattern 1: * * * 
            text = re.sub(r'\s*\*\s+\*\s+\*\s*', ' ', text)
            # Pattern 2: *** 
            text = re.sub(r'\*{3,}', ' ', text)
            # Pattern 3: bất kỳ tổ hợp * nào
            text = re.sub(r'(?:\s*\*\s*){3,}', ' ', text)
            text = text.strip()
            
            # Nếu dòng chỉ toàn dấu * thì bỏ qua
            if not text or text.replace('*', '').replace(' ', '') == '':
                if text_buffer:
                    final_output.extend(self.split_sentences(" ".join(text_buffer)))
                    text_buffer = []
                prev_type = 'SEPARATOR'
                continue
            
            # Detector
            is_bullet_char = re.match(r'^[-+]\s+', text) or re.match(r'^\d+\.\s+', text)
            is_meta_keyword = any(k in text for k in self.meta_keywords)
            is_library_code = re.match(r'^\d{3}\.\d+', text) or re.search(r'dc\s*22', text)
            is_physical_desc = re.match(r'^\d+\s*(tr\.|tr;|trang|p\.|cm)', text, re.IGNORECASE)

            # Xác định loại dòng
            current_type = 'TEXT'
            
            # Logic nhận diện Header
            # 1. Font to hẳn + viết hoa
            is_big_header = (size >= HEADER_THRESHOLD and text.isupper())
            # 2. Font cỡ thường nhưng viết hoa toàn bộ cả dòng (Sub-header) và ngắn (dưới 20 từ)
            is_sub_header = (text.isupper() and size >= body_size and len(text.split()) < 20)

            if is_bullet_char or is_meta_keyword or is_library_code or is_physical_desc:
                current_type = 'META'
            elif is_big_header or is_sub_header: 
                current_type = 'HEADER'

            # Logic gộp/tách dòng
            should_merge_meta = False
            if prev_type == 'META' and final_output:
                last_line = final_output[-1]
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
                    
                    # Dòng hiện tại bắt đầu viết thường hoặc số
                    if text[0].islower() or text[0].isdigit() or text.startswith('['):
                        should_merge = True
                    # Dòng trước kết thúc bằng tên viết tắt (Vd: H.L., T.P., A.)
                    # Regex này bắt các trường hợp đuôi là: " L.", " H.L.", " A.B.C.", "p.", "q.", "tp."
                    elif re.search(r'(?:^|[\s.])([a-zA-Z]{1,3}\.)$', prev_line):
                        should_merge = True
                    # Dòng trước kết thúc bằng dấu phẩy hoặc gạch nối
                    elif prev_line.endswith(',') or prev_line.endswith('-') or prev_line.endswith('–'):
                        should_merge = True

                if should_merge:
                    # Nếu nối dòng có dấu gạch nối ở cuối (ngắt từ), xóa gạch nối đi
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


if __name__ == "__main__":
    input_file = os.path.join("book", "Đồng Bằng sông Cửu Long Nét sinh hoạt xưa và văn minh miệt vườn.pdf") 
    output_file = "format_text.txt"
    cleaner = UltimatePDFCleaner()
    cleaner.extract_and_clean(input_file, output_file)