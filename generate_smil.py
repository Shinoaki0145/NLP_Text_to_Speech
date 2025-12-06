import re
from xml.etree.ElementTree import Element, SubElement, tostring, ElementTree
from xml.dom import minidom

def create_main_xml(input_file, output_file, metadata):
    """
    Tạo file main.xml theo chuẩn DAISY v3 từ file text đã format
    
    Args:
        input_file: Đường dẫn file format_text.txt
        output_file: Đường dẫn file main.xml đầu ra
        metadata: Dictionary chứa thông tin metadata của sách
    """
    
    # Đọc nội dung file text
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Tạo root element
    dtbook = Element('dtbook', {
        'xmlns': 'http://www.daisy.org/z3986/2005/dtbook/',
        'version': '2005-3',
        'xml:lang': 'vi'
    })
    
    # Tạo phần head với metadata
    head = SubElement(dtbook, 'head')
    
    # Thêm các metadata bắt buộc
    meta_fields = {
        'dc:Title': metadata.get('title', ''),
        'dc:Creator': metadata.get('creator', ''),
        'dc:Subject': metadata.get('subject', ''),
        'dc:Description': metadata.get('description', ''),
        'dc:Publisher': metadata.get('publisher', ''),
        'dc:Date': metadata.get('date', ''),
        'dc:Source': metadata.get('source', ''),
        'dc:Language': metadata.get('language', 'vi'),
    }
    
    for name, content in meta_fields.items():
        if content:  # Chỉ thêm nếu có nội dung
            meta = SubElement(head, 'meta')
            meta.set('name', name)
            meta.set('content', content)
    
    # Thêm metadata tùy chọn
    if metadata.get('thumb'):
        meta = SubElement(head, 'meta')
        meta.set('name', 'thumb')
        meta.set('content', metadata['thumb'])
    
    if metadata.get('note'):
        meta = SubElement(head, 'meta')
        meta.set('name', 'dc:Note')
        meta.set('content', metadata['note'])
    
    # Tạo phần book
    book = SubElement(dtbook, 'book')
    
    # Tạo frontmatter (phần đầu sách)
    frontmatter = SubElement(book, 'frontmatter')
    doctitle = SubElement(frontmatter, 'doctitle')
    doctitle.text = metadata.get('title', '')
    
    # Tạo bodymatter (nội dung chính)
    bodymatter = SubElement(book, 'bodymatter')
    
    # Xử lý nội dung từng dòng
    current_level = None
    current_section = None
    para_id = 1
    
    for line in lines:
        line = line.strip()
        
        if not line:  # Bỏ qua dòng trống
            continue
        
        # Phát hiện heading (tiêu đề chương/phần)
        # Giả sử các dòng ngắn, in hoa, hoặc có pattern đặc biệt là heading
        is_heading = detect_heading(line)
        
        if is_heading:
            # Tạo level1 mới cho chương
            current_level = SubElement(bodymatter, 'level1')
            h1 = SubElement(current_level, 'h1')
            h1.set('id', f'h1_{para_id}')
            h1.text = line
            para_id += 1
        else:
            # Nếu chưa có level1, tạo level1 mặc định
            if current_level is None:
                current_level = SubElement(bodymatter, 'level1')
                h1 = SubElement(current_level, 'h1')
                h1.set('id', f'h1_{para_id}')
                h1.text = 'Nội dung chính'
                para_id += 1
            
            # Thêm đoạn văn
            p = SubElement(current_level, 'p')
            p.set('id', f'p_{para_id}')
            p.text = line
            para_id += 1
    
    # Chuyển đổi sang string với format đẹp
    xml_str = prettify_xml(dtbook)
    
    # Ghi ra file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<!DOCTYPE dtbook PUBLIC "-//NISO//DTD dtbook 2005-3//EN" '
                '"http://www.daisy.org/z3986/2005/dtbook-2005-3.dtd">\n')
        f.write(xml_str)
    
    print(f"Đã tạo file {output_file} thành công!")
    print(f"Tổng số đoạn văn: {para_id - 1}")


def detect_heading(line):
    """
    Phát hiện xem dòng có phải là tiêu đề không
    """
    # Tiêu đề thường:
    # - Ngắn hơn 100 ký tự
    # - In hoa toàn bộ hoặc phần lớn
    # - Không kết thúc bằng dấu chấm
    
    if len(line) > 100:
        return False
    
    # Kiểm tra in hoa
    upper_chars = sum(1 for c in line if c.isupper())
    total_alpha = sum(1 for c in line if c.isalpha())
    
    if total_alpha > 0 and upper_chars / total_alpha > 0.7:
        return True
    
    # Pattern tiêu đề thường gặp
    heading_patterns = [
        r'^CHƯƠNG\s+[IVX\d]+',  # Chương I, II, III...
        r'^PHỤ\s+LỤC',
        r'^MỤC\s+LỤC',
        r'^LỜI\s+',
        r'^PHẦN\s+',
    ]
    
    for pattern in heading_patterns:
        if re.match(pattern, line, re.IGNORECASE):
            return True
    
    return False


def prettify_xml(elem):
    """
    Format XML với indentation đẹp
    """
    rough_string = tostring(elem, encoding='utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ", encoding='utf-8').decode('utf-8').split('\n', 1)[1]


# Ví dụ sử dụng
if __name__ == "__main__":
    # Metadata cho sách "Đồng Bằng Sông Cửu Long"
    metadata = {
        'title': 'Đồng Bằng Sông Cửu Long - Nét Sinh Hoạt Xưa & Văn Minh Miệt Vườn',
        'creator': 'Sơn Nam',
        'subject': 'Văn học & Tiểu thuyết',
        'description': 'Tác phẩm biên khảo về đồng bằng sông Cửu Long, văn hóa và sinh hoạt truyền thống của vùng đất Nam Bộ',
        'publisher': 'NXB Trẻ',
        'date': '2013',
        'source': '9786041266001',
        'language': 'vi',
        'thumb': 'https://example.com/cover.jpg',  # Thay bằng URL ảnh bìa thực tế
    }
    
    # Tạo file main.xml
    create_main_xml(
        input_file='text_clean.txt',
        output_file='main.xml',
        metadata=metadata
    )