import textgrid
import os
import re
from pathlib import Path
import xml.etree.ElementTree as ET
from xml.dom import minidom

# --- CẤU HÌNH ---
TEXT_DIR = "corpus"       
GRID_DIR = "fixed_output" 
OUTPUT_DIR = "xml_smil_output" 

START_NUM = 1
END_NUM = 17
SEARCH_WINDOW = 5  # Phạm vi tìm kiếm từ trong Grid (đề phòng lệch nhẹ)
# ----------------

def clean_word(w):
    """Chuẩn hóa từ để so sánh: chữ thường, bỏ dấu câu"""
    return re.sub(r'[^\w\s]', '', w).strip().lower()

def format_time(seconds):
    """Format thời gian cho SMIL (12.345s)"""
    return f"{seconds:.3f}s"

def prettify_xml(elem):
    """Làm đẹp output XML"""
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def generate_files():
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    print(f"🚀 Bắt đầu tạo SMIL/XML (Logic Match nội dung) từ {START_NUM:02d} đến {END_NUM:02d}...")

    for i in range(START_NUM, END_NUM + 1):
        file_id = f"{i:02d}"
        text_path = os.path.join(TEXT_DIR, f"{file_id}.txt")
        grid_path = os.path.join(GRID_DIR, f"{file_id}.TextGrid") 
        
        xml_out_path = os.path.join(OUTPUT_DIR, f"{file_id}.xml")
        smil_out_path = os.path.join(OUTPUT_DIR, f"{file_id}.smil")

        if not os.path.exists(text_path) or not os.path.exists(grid_path):
            print(f"⚠️  Bỏ qua {file_id}: Thiếu file.")
            continue

        # 1. Đọc TextGrid & Lọc intervals
        try:
            tg = textgrid.TextGrid.fromFile(grid_path)
            word_tier = tg.getFirst('words') if 'words' in tg.getNames() else tg[0]
            # Lọc interval rỗng/silence
            intervals = [i for i in word_tier if i.mark not in ["", None, "sp", "sil", "<sil>", "[bracketed]"]]
        except Exception as e:
            print(f"❌ Lỗi TextGrid {file_id}: {e}")
            continue

        # 2. Đọc file Text
        with open(text_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # --- Cấu trúc XML ---
        xml_root = ET.Element("sentences", {"id": file_id})
        
        # --- Cấu trúc SMIL ---
        smil_root = ET.Element("smil", {
            "xmlns": "http://www.w3.org/2001/SMIL20/Language", 
            "xmlns:epub": "http://www.idpf.org/2007/ops"
        })
        
        # --- METADATA (Đã thêm theo yêu cầu) ---
        smil_head = ET.SubElement(smil_root, "head")
        metadata = [
            ("dc:Title", "Đồng Bằng Sông Cửu Long - Nét Sinh Hoạt Xưa & Văn Minh Miệt Vườn"),
            ("dc:Creator", "Sơn Nam"),
            ("dc:Subject", "Biên khảo"),
            ("dc:Description", "Tác phẩm biên khảo về đồng bằng sông Cửu Long, văn hóa và sinh hoạt truyền thống của vùng đất Nam Bộ"),
            ("dc:Publisher", "NXB Trẻ"),
            ("dc:Date", "2013"),
            ("dc:Source", "9786041266001"),
            ("dc:Language", "vi"),
            ("thumb", "Bìa sách.png")
        ]
        for name, content in metadata:
            ET.SubElement(smil_head, "meta", {"name": name, "content": content})
        # ---------------------------------------

        smil_body = ET.SubElement(smil_root, "body")
        smil_seq = ET.SubElement(smil_body, "seq", {
            "id": f"seq_{file_id}",
            "epub:textref": f"{file_id}.html"
        })

        grid_idx = 0 # Con trỏ duyệt interval trong Grid
        
        # 3. Logic Mapping: So khớp từng từ
        for line_idx, line in enumerate(lines):
            line_content = line.strip()
            if not line_content: continue

            # Chuẩn bị text để tách từ (Giống logic clean cũ)
            temp_line = line_content.replace("-", " ").replace("/", " ")
            temp_line = re.sub(r"\[\d+\]", "", temp_line)
            temp_line = re.sub(r'(?<=\d)\.(?=\d)', ' ', temp_line)
            temp_line = re.sub(r'(?<=[a-zA-Z])\.(?=[a-zA-Z])', ' ', temp_line)
            
            # Danh sách từ cần tìm trong câu hiện tại
            words_in_line = temp_line.split()
            clean_words_in_line = [clean_word(w) for w in words_in_line if clean_word(w)]
            
            if not clean_words_in_line: continue

            start_time = None
            end_time = None
            
            # Duyệt qua từng từ trong câu văn bản để tìm trong Grid
            # Logic: Tìm từ khớp đầu tiên để lấy Start, cập nhật liên tục để lấy End
            matches_found = 0
            
            for target_word in clean_words_in_line:
                # Tìm target_word trong Grid, trong khoảng SEARCH_WINDOW
                found_at_idx = -1
                
                # Quét từ vị trí hiện tại của Grid đi tới
                for offset in range(SEARCH_WINDOW):
                    if grid_idx + offset < len(intervals):
                        grid_word = clean_word(intervals[grid_idx + offset].mark)
                        if grid_word == target_word:
                            found_at_idx = grid_idx + offset
                            break
                
                if found_at_idx != -1:
                    # TÌM THẤY TỪ
                    matches_found += 1
                    current_interval = intervals[found_at_idx]
                    
                    # Nếu là từ khớp đầu tiên của câu -> Lấy Start Time
                    if start_time is None:
                        start_time = current_interval.minTime
                    
                    # Luôn cập nhật End Time (để lấy maxTime của từ cuối cùng tìm thấy)
                    end_time = current_interval.maxTime
                    
                    # Di chuyển con trỏ Grid đến ngay sau từ vừa tìm thấy
                    # Để từ tiếp theo trong vòng lặp sẽ tìm tiếp từ đó trở đi
                    grid_idx = found_at_idx + 1
                else:
                    # print (f"   ⚠️  Notice {file_id}: Không tìm thấy từ '{target_word}' trong Grid tại dòng '{line_content[:20]}, {start_time, end_time}...'")
                    pass
            
            # Nếu trong câu không tìm thấy bất kỳ từ nào khớp (Lỗi nặng)
            if start_time is None or end_time is None:
                print(f"   ⚠️  Warning {file_id}: Không khớp được dòng '{line_content[:20]}...'")
                # Fallback: Lấy thời gian tiếp nối của câu trước (nếu cần) hoặc bỏ qua
                continue

            # --- GHI KẾT QUẢ ---
            # XML
            sent_elem = ET.SubElement(xml_root, "sentence")
            sent_elem.set("id", f"s{line_idx + 1}")
            sent_elem.set("start", f"{start_time:.3f}")
            sent_elem.set("end", f"{end_time:.3f}")
            sent_elem.text = line_content

            # SMIL
            par = ET.SubElement(smil_seq, "par", {"id": f"par_{line_idx + 1}"})
            ET.SubElement(par, "text", {"src": f"{file_id}.html#s{line_idx + 1}"})
            ET.SubElement(par, "audio", {
                "src": f"{file_id}.mp3",
                "clipBegin": format_time(start_time),
                "clipEnd": format_time(end_time)
            })

        # Ghi file
        with open(xml_out_path, "w", encoding="utf-8") as f:
            f.write(prettify_xml(xml_root))
        with open(smil_out_path, "w", encoding="utf-8") as f:
            f.write(prettify_xml(smil_root))
            
        print(f"✅ Xong {file_id}")

    print("\n🎉 HOÀN TẤT!")

if __name__ == "__main__":
    generate_files()