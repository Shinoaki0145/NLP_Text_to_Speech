import re
import os
import unicodedata
import logging
import pdfplumber
from collections import Counter

# Tắt log rác
logging.getLogger("pdfminer").setLevel(logging.ERROR)

class UltimatePDFCleaner:
    def __init__(self):
        self.garbage_phrases = [
            "Tủ sách", "Ebook miễn phí", "hoccachlamgiau", 
            "Created by", "Watermark", "sacngoc", "Ồ Ằ", "Ổ Ầ", "Ồ Ầ", "Ể "
        ]
        self.meta_keywords = [
            "Copyright", "Cataloging", "biên khảo", "NXB", "NHÀ XUẤT BẢN", 
            "Publishing House", "BIỂU GHI", "THƯ VIỆN"
        ]
        # Các từ/ký tự báo hiệu Metadata chưa kết thúc (để nối dòng)
        self.meta_connectors = ["-", "--", "–", "và", ":", ","]
    
    def clean_string(self, text):
        if not text: return ""
        text = unicodedata.normalize('NFKC', text)
        
        # 1. XÓA RÁC ĐẦU DÒNG & CUỐI DÒNG
        text = re.sub(r'^[\s•●_]+', '', text)
        
        # 2. XÓA CỤM TỪ RÁC TRONG DÒNG
        for phrase in self.garbage_phrases:
            text = text.replace(phrase, "")

        # 3. FIX LỖI DẤU CÂU CÁCH XA (Vườn , -> Vườn,)
        text = re.sub(r'\s+([,.:;!?])', r'\1', text)
        
        # # Chuẩn hóa bên trong ngoặc kép
        # text = re.sub(r'"\s+', '"', text)
        # text = re.sub(r'\s+"', '"', text)

        # # Xử lý bên ngoài dấu mở "
        # text = re.sub(r'(?<=[^\s(])"', ' "', text)

        # # Xử lý bên ngoài dấu đóng "
        # text = re.sub(r'"(?=\w)', '" ', text)
        # # text = re.sub(r'(?<=[^\s(])“', ' “', text)
        
        
        # A. Xử lý ngoặc kép THẲNG (")
        # Xóa space thừa bên trong: " ABC " -> "ABC"
        text = re.sub(r'"\s+', '"', text)
        text = re.sub(r'\s+"', '"', text)
        # Tách dính bên ngoài: abc"def -> abc "def
        text = re.sub(r'(?<=[^\s(])"', ' "', text)
        text = re.sub(r'"(?=\w)', '" ', text)

        # B. Xử lý ngoặc kép CONG/THÔNG MINH (Smart Quotes “ ”)
        # Xóa space thừa BÊN TRONG: “ Ra đi ” -> “Ra đi”
        text = re.sub(r'“\s+', '“', text)  # Xóa space sau dấu mở
        text = re.sub(r'\s+”', '”', text)  # Xóa space trước dấu đóng
        
        # Xử lý tách dính BÊN NGOÀI (Space separation)
        # Dấu mở “: Cần space phía trước (trừ khi ở đầu dòng hoặc sau ngoặc đơn)
        # Ví dụ: từ“ -> từ “
        text = re.sub(r'(?<=[^\s(])“', ' “', text)
    
        
        # Dấu đóng ”: Cần space phía sau (nếu sau đó là chữ liền)
        # Ví dụ: ”là -> ” là
        text = re.sub(r'”(?=\w)', '” ', text)
        

        # Tách (Tựa đề) sang dòng riêng
        text = re.sub(r'^\(([^)]+)\)\s*', r'(\1)\n', text)
        
        return text.strip()
    
    
    def should_merge_with_next(self, current_text, next_text):
        if not current_text or not next_text:
            return False
        
        # Pattern 1: Dòng kết thúc bằng chữ viết tắt (H.L., B.Ph., etc.)
        # VD: "Theo H.L." + "Jammes" -> cần nối
        if re.search(r'\b[A-Z]\.(?:[A-Z]\.)*$', current_text):
            # Dòng tiếp theo bắt đầu bằng chữ hoa (tên họ)
            if next_text and next_text[0].isupper():
                return True
        
        # Pattern 2: Dòng kết thúc bằng tên có dấu phẩy + viết tắt
        # VD: "Groslier, L." + "Malleret" -> cần nối
        if re.search(r',\s*[A-Z]\.(?:[A-Z]\.)*$', current_text):
            if next_text and next_text[0].isupper():
                return True
        
        # Pattern 3: Dòng kết thúc bằng chữ thường (câu chưa xong)
        if current_text[-1].islower() or current_text[-1].isdigit():
            return True
            
        return False
    

    def split_sentences(self, text):
        if not text: return []
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace('|||NEWLINE|||', '\n')
        
        def protect_match(match):
            return match.group().replace('.', '<PR_DOT>')
        
        text = re.sub(r'(?<!\w)[A-Z][a-zA-Z]{0,2}\.(?=\s)', protect_match, text)
        
        viet_upper = "ÁÀẢÃẠÂẤẦẨẪẬĂẮẰẲẴẶÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ" 
        pattern = r'(?<=[.?!])\s+(?=[A-Z%s"\'\«\(\“\‘])' % viet_upper
        
        # pattern = r'(?<=[.?!])\s+(?=[A-ZÁÀẢÃẠÂẤẦẨẪẬĂẮẰẲẴẶÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴĐ"\'\«\(\"])'

        sentences = re.split(pattern, text)
        
        final_sentences = []
        for s in sentences:
            if s.strip():
                # Trả lại dấu chấm ban đầu
                restored = s.replace('<PR_DOT>', '.')
                final_sentences.append(restored.strip())
        
        
        return final_sentences
        # return [s.strip() for s in sentences if s.strip()]

    def get_lines_with_meta(self, page):
        words = page.extract_words(extra_attrs=['size'])
        if not words: return []

        lines = []
        current_line = [words[0]]
        
        for word in words[1:]:
            if abs(word['top'] - current_line[-1]['top']) < 3:
                current_line.append(word)
            else:
                lines.append(current_line)
                current_line = [word]
        lines.append(current_line)

        processed_lines = []
        for line_words in lines:
            text = " ".join([w['text'] for w in line_words])
            max_size = max([w['size'] for w in line_words])
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
        """Bước cuối: Nối địa danh bị gãy (T.P. Hồ Chí Minh)"""
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
            
            # Xóa hoàn toàn các pattern ***
            # Pattern 1: * * * (có space)
            text = re.sub(r'\s*\*\s+\*\s+\*\s*', ' ', text)
            # Pattern 2: *** (không có space)
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
            
            # --- DETECTORS ---
            is_bullet_char = re.match(r'^[-+]\s+', text) or re.match(r'^\d+\.\s+', text)
            is_meta_keyword = any(k in text for k in self.meta_keywords)
            is_library_code = re.match(r'^\d{3}\.\d+', text) or re.search(r'dc\s*22', text)
            
            # Xác định loại dòng
            current_type = 'TEXT'
            
            # Logic nhận diện Header cải tiến:
            # 1. Font to hẳn + Viết hoa
            is_big_header = (size >= HEADER_THRESHOLD and text.isupper())
            # 2. Font cỡ thường nhưng Viết hoa toàn bộ cả dòng (Sub-header) & ngắn (dưới 20 từ)
            is_sub_header = (text.isupper() and size >= body_size and len(text.split()) < 20)

            if is_bullet_char or is_meta_keyword or is_library_code:
                current_type = 'META'
            elif is_big_header or is_sub_header: 
                current_type = 'HEADER'

            # --- LOGIC GỘP METADATA ---
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

            # --- XỬ LÝ THEO LOẠI DÒNG ---
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

            # else: # TEXT
            #     if text_buffer and (text[0].islower() or text[0].isdigit()):
            #         text_buffer[-1] = text_buffer[-1] + " " + text
            #     else:
            #         text_buffer.append(text)
            #     prev_type = 'TEXT'
            
            
            else: # TEXT
                should_merge = False
                
                if text_buffer:
                    prev_line = text_buffer[-1].strip()
                    
                    # CHECK 1: Dòng hiện tại bắt đầu viết thường hoặc số (Logic cũ)
                    if text[0].islower() or text[0].isdigit():
                        should_merge = True
                    
                    # CHECK 2 (MỚI): Dòng trước kết thúc bằng tên viết tắt (Vd: H.L., T.P., A.)
                    # Regex này bắt các trường hợp đuôi là: " L.", " H.L.", " A.B.C."
                    elif re.search(r'(?:^|[\s.])([A-Z][a-zA-Z]{0,2}\.)$', prev_line):
                        should_merge = True

                    # CHECK 3 (Bổ sung): Dòng trước kết thúc bằng dấu phẩy hoặc gạch nối
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
            
            

        # Đẩy buffer cuối cùng
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

            print("\nĐang phân tích và làm sạch...")
            body_size = self.analyze_font_structure(all_lines_with_meta)
            final_lines = self.process_hybrid_structure(all_lines_with_meta, body_size)
            
            with open(output_txt_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(final_lines))
            print(f"Hoàn tất! File lưu tại: {output_txt_path}")
        except Exception as e:
            print(f"\nLỗi: {e}")


# Cách dùng
input_file = os.path.join("book", "Đồng Bằng sông Cửu Long Nét sinh hoạt xưa và văn minh miệt vườn.pdf") 
output_file = "format_text.txt"

if __name__ == "__main__":
    cleaner = UltimatePDFCleaner()
    cleaner.extract_and_clean(input_file, output_file)