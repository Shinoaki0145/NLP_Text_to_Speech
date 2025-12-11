import textgrid
import re
from pathlib import Path

# --- CẤU HÌNH ---
INPUT_GRID_DIR = "output"       # Thư mục chứa file TextGrid lỗi
INPUT_TEXT_DIR = "corpus"       # Thư mục chứa file Text gốc
OUTPUT_DIR = "fixed_output"     # Thư mục chứa kết quả
SEARCH_RANGE = 10             # Phạm vi tìm kiếm mỏ neo
# ----------------

def clean_word(w):
    """Chuẩn hóa từ: chữ thường, bỏ dấu câu"""
    return re.sub(r'[^\w\s]', '', w).strip().lower()
def find_anchor_in_text(clean_text_words, text_ptr, anchor_word, anchor_context, search_range=20):
    """
    Tìm vị trí chính xác của mỏ neo trong text, tránh bắt nhầm từ lặp lại.
    """
    candidates = []
    
    # 1. Tìm tất cả các vị trí có thể là mỏ neo
    for j in range(text_ptr, min(len(clean_text_words), text_ptr + search_range)):
        if clean_text_words[j] == anchor_word:
            candidates.append(j)
            
    if not candidates:
        return -1

    # 2. Nếu có context (từ sau mỏ neo trong Grid), dùng nó để lọc
    if anchor_context:
        for idx in candidates:
            # Kiểm tra từ ngay sau ứng viên trong Text có khớp context không
            if idx + 1 < len(clean_text_words):
                text_next_word = clean_text_words[idx + 1]
                if text_next_word == anchor_context:
                    return idx # Tìm thấy cặp khớp hoàn hảo (ráo -> riết)
    
    # 3. Fallback: Nếu không có context hoặc không khớp context nào
    # Trả về ứng viên xa nhất có thể (để chừa chỗ điền vào <unk>)
    # Hoặc trả về ứng viên đầu tiên (tùy chiến thuật, ở đây ta ưu tiên context trên hết)
    return candidates[0]

def process_single_pair(grid_path, text_path, save_path):
    """Hàm xử lý logic Anchor & Fill cho 1 cặp file"""
    
    # 1. Đọc Text gốc
    try:
        with open(text_path, 'r', encoding='utf-8') as f:
            content = f.read()

        content = content.replace("-", " ")
        content = content.replace("/", " ")
        content = re.sub(r"\[\d+\]", "", content)
        content = re.sub(r'(?<=\d)\.(?=\d)', ' ', content)
        content = re.sub(r'(?<=[a-zA-Z])\.(?=[a-zA-Z])', ' ', content)
        raw_text_words = content.split() 
        clean_text_words = [clean_word(w) for w in raw_text_words]
    except Exception as e:
        print(f"❌ Lỗi đọc file Text {text_path}: {e}")
        return

    # 2. Đọc TextGrid
    try:
        tg = textgrid.TextGrid.fromFile(grid_path)
        try:
            word_tier = tg.getFirst('words')
        except ValueError:
            word_tier = tg[0]
    except Exception as e:
        print(f"❌ Lỗi đọc file Grid {grid_path}: {e}")
        return

    # Lọc interval (bỏ silence)
    intervals = [i for i in word_tier if i.mark not in [""]]
    
    text_ptr = 0 
    fixed_count = 0
    grid_idx = 0

    # Logic "Mỏ neo và Lấp đầy"
    while grid_idx < len(intervals):
        current_interval = intervals[grid_idx]
        current_mark = clean_word(current_interval.mark)
        # print(f"\n[GRID] idx={grid_idx}, raw='{current_interval.mark}', clean='{current_mark}', text_ptr={text_ptr}")
        # --- TRƯỜNG HỢP <UNK> ---
        if current_interval.mark == "<unk>":
            # Tìm mỏ neo trong Grid (Anchor)
            anchor_grid_idx = -1
            anchor_word = ""
            anchor_context = None # Từ đứng SAU mỏ neo để verify

            # Quét các interval tiếp theo để tìm từ KHÔNG phải <unk>
            for offset in range(1, 20): # Tìm xa nhất 20 từ
                if grid_idx + offset < len(intervals):
                    check_int = intervals[grid_idx + offset]
                    if check_int.mark != "<unk>":
                        anchor_grid_idx = grid_idx + offset
                        anchor_word = clean_word(check_int.mark)

                        if grid_idx + offset + 1 < len(intervals):
                            next_int = intervals[grid_idx + offset + 1]
                            if next_int.mark != "<unk>":
                              anchor_context = clean_word(next_int.mark)  
                        break
            
            # Định vị mỏ neo trong Text Gốc
            target_text_idx = -1
            if anchor_grid_idx != -1:
                target_text_idx = find_anchor_in_text(
                    clean_text_words, 
                    text_ptr, 
                    anchor_word, 
                    anchor_context, # Truyền context vào đây
                    search_range=SEARCH_RANGE
                )
            
            # Lấp đầy (Fill)
            if target_text_idx != -1 and target_text_idx >= text_ptr:
                num_unks = anchor_grid_idx - grid_idx
                for k in range(num_unks):
                    # Logic kiểm tra an toàn cũ vẫn giữ nguyên
                    if (text_ptr + k) < target_text_idx:
                        word_to_fill = raw_text_words[text_ptr + k]
                    else:
                        word_to_fill = "?" # Vẫn cần cái này cho trường hợp lệch số lượng

                    intervals[grid_idx + k].mark = word_to_fill
                    # print(f"   -> Điền: {word_to_fill}")
                    fixed_count += 1
                
                grid_idx = anchor_grid_idx
                text_ptr = target_text_idx
            else:
                # Không tìm thấy neo, điền mù
                if text_ptr < len(raw_text_words):
                    intervals[grid_idx].mark = raw_text_words[text_ptr]
                    text_ptr += 1
                    grid_idx += 1
                    fixed_count += 1
                else:
                    grid_idx += 1

        # --- TRƯỜNG HỢP TỪ THƯỜNG ---
        else:
            if text_ptr < len(clean_text_words):
                if current_mark == clean_text_words[text_ptr]:
                    if current_interval.mark != raw_text_words[text_ptr]:
                        current_interval.mark = raw_text_words[text_ptr]
                    text_ptr += 1
                else:
                    # Sync lại nếu lệch
                    found_resync = False
                    for search_offset in range(-10, 10):
                        if text_ptr + search_offset < len(clean_text_words):
                             if clean_text_words[text_ptr + search_offset] == current_mark:
                                 text_ptr += search_offset + 1
                                 found_resync = True
                                 break
                    if not found_resync:
                        text_ptr += 1
            grid_idx += 1

    # Lưu file
    tg.write(save_path)
    print(f"✅ Đã xử lý: {Path(save_path).name} | Sửa {fixed_count} lỗi.")

def main():
    # Tạo thư mục output nếu chưa có
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    
    # Lấy danh sách file trong thư mục grid
    grid_files = sorted(Path(INPUT_GRID_DIR).glob("*.TextGrid"))
    
    print(f"Tìm thấy {len(grid_files)} file TextGrid cần xử lý.\n")

    for grid_file in grid_files:
        # Giả định file text cùng tên (ví dụ: 01.TextGrid -> 01.txt)
        text_filename = grid_file.stem + ".txt" # .stem lấy tên không đuôi
        text_file = Path(INPUT_TEXT_DIR) / text_filename
        
        output_path = Path(OUTPUT_DIR) / grid_file.name

        if text_file.exists():
            process_single_pair(str(grid_file), str(text_file), str(output_path))
        else:
            print(f"⚠️  Bỏ qua: Không tìm thấy file text gốc cho {grid_file.name} (Cần file: {text_filename})")

    print("\n--- HOÀN TẤT TOÀN BỘ ---")

if __name__ == "__main__":
    main()