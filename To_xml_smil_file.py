import textgrid
import os
import re
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom

# --- CẤU HÌNH ---
TEXT_DIR = "corpus"       
GRID_DIR = "fixed_output" 
OUTPUT_DIR = "xml_smil_output"  # Đổi tên folder output cho dễ phân biệt

START_NUM = 1
END_NUM = 17
SEARCH_WINDOW = 5
# ----------------

def clean_word(w):
    return re.sub(r'[^\w\s]', '', w).strip().lower()

def format_time(seconds):
    """Format thời gian chuẩn SMIL (npt=12.345s hoặc 12.345s)"""
    return f"{seconds:.3f}s"

def prettify_xml(elem, doc_type_string=None):
    """Làm đẹp output XML và thêm DOCTYPE"""
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")
    
    # Loại bỏ dòng xml declaration mặc định của minidom nếu muốn tự thêm control
    # Nhưng thường giữ lại <?xml ...?> là tốt nhất.
    
    if doc_type_string:
        # Chèn DOCTYPE vào sau dòng <?xml ...?>
        lines = pretty_xml.split('\n')
        if lines[0].startswith('<?xml'):
            lines.insert(1, doc_type_string)
        else:
            lines.insert(0, doc_type_string)
        return '\n'.join(lines)
    return pretty_xml

def generate_files():
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    print(f"🚀 Bắt đầu tạo DAISY 3 (DTBook + SMIL) từ {START_NUM:02d} đến {END_NUM:02d}...")

    for i in range(START_NUM, END_NUM + 1):
        file_id = f"{i:02d}"
        text_path = os.path.join(TEXT_DIR, f"{file_id}.txt")
        grid_path = os.path.join(GRID_DIR, f"{file_id}.TextGrid") 
        
        # DAISY 3 file nội dung thường có đuôi .xml (DTBook)
        xml_out_path = os.path.join(OUTPUT_DIR, f"{file_id}.xml")
        smil_out_path = os.path.join(OUTPUT_DIR, f"{file_id}.smil")

        if not os.path.exists(text_path) or not os.path.exists(grid_path):
            print(f"⚠️  Bỏ qua {file_id}: Thiếu file.")
            continue

        try:
            tg = textgrid.TextGrid.fromFile(grid_path)
            word_tier = tg.getFirst('words') if 'words' in tg.getNames() else tg[0]
            intervals = [i for i in word_tier if i.mark not in ["", None, "sp", "sil", "<sil>", "[bracketed]"]]
        except Exception as e:
            print(f"❌ Lỗi TextGrid {file_id}: {e}")
            continue

        with open(text_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # --- 1. Cấu trúc DTBOOK XML (Thay cho cấu trúc tự chế) ---
        # DAISY 3 yêu cầu root là dtbook
        dtbook_ns = "http://www.daisy.org/z3986/2005/dtbook/"
        ET.register_namespace('', dtbook_ns) # Đăng ký namespace mặc định để không bị hiện ns0:
        
        xml_root = ET.Element("dtbook", {
            "xmlns": dtbook_ns,
            "version": "2005-3",
            "xml:lang": "vi"
        })
        
        # Phần head của DTBook
        dt_head = ET.SubElement(xml_root, "head")
        # (Có thể thêm meta dtb:uid tại đây nếu cần thiết)

        dt_book = ET.SubElement(xml_root, "book")
        dt_body = ET.SubElement(dt_book, "body")
        dt_level1 = ET.SubElement(dt_body, "level1") # Cấu trúc tối thiểu cần level1
        
        # --- 2. Cấu trúc SMIL (Chuẩn SMIL 2.0 cho DAISY) ---
        smil_ns = "http://www.w3.org/2001/SMIL20/Language"
        ET.register_namespace('', smil_ns)
        
        smil_root = ET.Element("smil", {
            "xmlns": smil_ns,
            "xml:lang": "vi"
        })
        
        smil_head = ET.SubElement(smil_root, "head")
        
        ET.SubElement(smil_head, "meta", {
            "name": "dtb:uid", 
            "content":"978-604-1-12853-8"
        })
    
        # Layout (Bắt buộc với một số trình đọc DAISY phần cứng)
        layout = ET.SubElement(smil_head, "layout")
        region = ET.SubElement(layout, "region", {"id": "txtView"})

        smil_body = ET.SubElement(smil_root, "body")
        # DAISY dùng <seq> bình thường, không có epub:textref
        smil_seq = ET.SubElement(smil_body, "seq", {"id": f"seq_{file_id}"})

        grid_idx = 0 
        
        # --- LOGIC MAPPING ---
        for line_idx, line in enumerate(lines):
            line_content = line.strip()
            if not line_content: continue

            # Logic tìm từ (Giữ nguyên logic của bạn)
            temp_line = line_content.replace("-", " ").replace("/", " ")
            temp_line = re.sub(r"\[\d+\]", "", temp_line)
            temp_line = re.sub(r'(?<=\d)\.(?=\d)', ' ', temp_line)
            temp_line = re.sub(r'(?<=[a-zA-Z])\.(?=[a-zA-Z])', ' ', temp_line)
            
            words_in_line = temp_line.split()
            clean_words_in_line = [clean_word(w) for w in words_in_line if clean_word(w)]
            
            if not clean_words_in_line: continue

            start_time = None
            end_time = None
            matches_found = 0
            
            for target_word in clean_words_in_line:
                found_at_idx = -1
                for offset in range(SEARCH_WINDOW):
                    if grid_idx + offset < len(intervals):
                        grid_word = clean_word(intervals[grid_idx + offset].mark)
                        if grid_word == target_word:
                            found_at_idx = grid_idx + offset
                            break
                
                if found_at_idx != -1:
                    matches_found += 1
                    current_interval = intervals[found_at_idx]
                    if start_time is None: start_time = current_interval.minTime
                    end_time = current_interval.maxTime
                    grid_idx = found_at_idx + 1

            if start_time is None or end_time is None:
                print(f"   ⚠️  Warning {file_id}: Không khớp dòng '{line_content[:20]}...'")
                continue

            # ID cho câu
            sent_id = f"s{line_idx + 1}"

            # --- GHI DTBOOK XML ---
            # Dùng thẻ <p> hoặc <sent> (DAISY khuyến nghị <sent> bên trong <p> cho sync mịn)
            # Ở đây dùng <p> bọc <sent> để đúng chuẩn nhất
            p_elem = ET.SubElement(dt_level1, "p")
            sent_elem = ET.SubElement(p_elem, "sent", {"id": sent_id})
            sent_elem.text = line_content

            # --- GHI SMIL ---
            par = ET.SubElement(smil_seq, "par", {"id": f"par_{line_idx + 1}"})
            
            # Text src trỏ về file XML (tên file xml + #ID)
            ET.SubElement(par, "text", {
                "src": f"{file_id}.xml#{sent_id}",
                "id": f"txt_{line_idx + 1}" 
            })
            
            # Audio
            ET.SubElement(par, "audio", {
                "src": f"{file_id}.mp3",
                "clipBegin": format_time(start_time),
                "clipEnd": format_time(end_time),
                "id": f"aud_{line_idx + 1}"
            })

        # --- XUẤT FILE ---
        
        # 1. Xuất DTBook XML với DOCTYPE chuẩn
        dtbook_doctype = '<!DOCTYPE dtbook PUBLIC "-//NISO//DTD dtbook 2005-3//EN" "http://www.daisy.org/z3986/2005/dtbook-2005-3.dtd">'
        with open(xml_out_path, "w", encoding="utf-8") as f:
            f.write(prettify_xml(xml_root, dtbook_doctype))

        # 2. Xuất SMIL với DOCTYPE chuẩn
        smil_doctype = '<!DOCTYPE smil PUBLIC "-//NISO//DTD SMIL 1.0//EN" "http://www.daisy.org/z3986/2005/smil-2005-2.dtd">'
        with open(smil_out_path, "w", encoding="utf-8") as f:
            f.write(prettify_xml(smil_root, smil_doctype))
            
        print(f"✅ Xong {file_id}")

    print("\n🎉 HOÀN TẤT CHUẨN DAISY 3!")

if __name__ == "__main__":
    generate_files()